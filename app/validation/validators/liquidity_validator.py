from app.config import settings
from app.infra.bybit_client import BybitClient
from .base_validator import BaseValidator, ValidationResult, ValidationStatus

# Gold perpetual futures on Bybit — typical spread is < 0.02%.
# These thresholds are intentionally conservative for live capital.
_SPREAD_WARN_PCT = 0.03   # 3 bps  — warn but still tradeable
_SPREAD_FAIL_PCT = 0.10   # 10 bps — spread too wide, execution cost unacceptable
_MIN_BID_DEPTH_USD = 50_000   # Minimum USD depth within 0.1% of mid on each side
_MAX_BOOK_IMBALANCE = 0.70    # If one side holds > 70% of near-book volume, signal thin market


class LiquidityValidator(BaseValidator):
    """
    Validate XAUUSDT orderbook liquidity before going live.

    Thin liquidity means larger-than-expected slippage on entry/exit.
    Extreme book imbalance can indicate a pending sweep — dangerous for
    market orders. All thresholds are calibrated for Bybit perpetual gold.
    """

    @property
    def layer_name(self) -> str:
        return "Liquidity"

    @property
    def weight(self) -> float:
        return 8

    async def validate(self) -> ValidationResult:
        checks = []
        passed = 0
        total = 3

        client = BybitClient(
            api_key=settings.BYBIT_API_KEY,
            api_secret=settings.BYBIT_API_SECRET,
            testnet=settings.BYBIT_USE_DEMO_DOMAIN,
        )

        try:
            ob = await client.fetch_orderbook(
                settings.PRIMARY_TRADING_SYMBOL, limit=20
            )
        except Exception as e:
            return ValidationResult(
                layer_name=self.layer_name,
                status=ValidationStatus.ERROR,
                score=0, checks_passed=0, checks_total=total,
                errors=[f"Orderbook fetch failed: {e}"],
            )
        finally:
            await client.close()

        bids = ob.get('bids', [])   # [[price, qty], ...]
        asks = ob.get('asks', [])

        if not bids or not asks:
            return ValidationResult(
                layer_name=self.layer_name,
                status=ValidationStatus.ERROR,
                score=0, checks_passed=0, checks_total=total,
                errors=["Empty orderbook returned"],
            )

        best_bid = bids[0][0]
        best_ask = asks[0][0]
        mid = (best_bid + best_ask) / 2.0

        # ----------------------------------------------------------------
        # Check 1: Bid-ask spread
        # ----------------------------------------------------------------
        spread_pct = ((best_ask - best_bid) / mid) * 100
        if spread_pct < _SPREAD_WARN_PCT:
            passed += 1
            checks.append({'check': 'Bid-Ask Spread', 'status': 'PASS',
                           'value': f"{spread_pct:.4f}%"})
        elif spread_pct < _SPREAD_FAIL_PCT:
            passed += 1
            checks.append({'check': 'Bid-Ask Spread', 'status': 'WARNING',
                           'value': f"{spread_pct:.4f}% (wide)",
                           'threshold': f"< {_SPREAD_WARN_PCT}%"})
        else:
            checks.append({'check': 'Bid-Ask Spread', 'status': 'FAIL',
                           'value': f"{spread_pct:.4f}% (too wide for live trading)",
                           'threshold': f"< {_SPREAD_FAIL_PCT}%"})

        # ----------------------------------------------------------------
        # Check 2: Near-book depth (USD value within 0.1% of mid, each side)
        # ----------------------------------------------------------------
        depth_band = mid * 0.001  # 0.1% of mid price
        bid_depth_usd = sum(p * q for p, q in bids if p >= mid - depth_band)
        ask_depth_usd = sum(p * q for p, q in asks if p <= mid + depth_band)

        min_depth = min(bid_depth_usd, ask_depth_usd)
        if min_depth >= _MIN_BID_DEPTH_USD:
            passed += 1
            checks.append({'check': 'Book Depth', 'status': 'PASS',
                           'value': (f"bid=${bid_depth_usd:,.0f} "
                                     f"ask=${ask_depth_usd:,.0f} within 0.1% of mid")})
        else:
            checks.append({'check': 'Book Depth', 'status': 'FAIL',
                           'value': (f"bid=${bid_depth_usd:,.0f} "
                                     f"ask=${ask_depth_usd:,.0f}"),
                           'threshold': f"≥ ${_MIN_BID_DEPTH_USD:,} on each side"})

        # ----------------------------------------------------------------
        # Check 3: Book imbalance — one-sided pressure signals a sweep risk
        # ----------------------------------------------------------------
        total_near = bid_depth_usd + ask_depth_usd
        if total_near > 0:
            bid_ratio = bid_depth_usd / total_near
            ask_ratio = ask_depth_usd / total_near
            dominant_side = 'bid' if bid_ratio > ask_ratio else 'ask'
            dominant_ratio = max(bid_ratio, ask_ratio)

            if dominant_ratio <= _MAX_BOOK_IMBALANCE:
                passed += 1
                checks.append({'check': 'Book Balance', 'status': 'PASS',
                               'value': f"bid {bid_ratio:.0%} / ask {ask_ratio:.0%}"})
            else:
                # Imbalance is advisory — WARNING not FAIL
                passed += 1
                checks.append({'check': 'Book Balance', 'status': 'WARNING',
                               'value': (f"{dominant_side} side dominates "
                                         f"({dominant_ratio:.0%})"),
                               'note': 'Potential sweep risk — use limit orders'})
        else:
            checks.append({'check': 'Book Balance', 'status': 'SKIP',
                           'note': 'Insufficient near-book depth to evaluate'})
            total -= 1

        score = (passed / total) * 100 if total > 0 else 0
        any_fail = any(c['status'] == 'FAIL' for c in checks)
        status = ValidationStatus.FAIL if any_fail else (
            ValidationStatus.WARNING if any(c['status'] == 'WARNING' for c in checks)
            else ValidationStatus.PASS
        )
        return ValidationResult(
            layer_name=self.layer_name,
            status=status,
            score=score,
            checks_passed=passed,
            checks_total=total,
            details=checks,
        )
