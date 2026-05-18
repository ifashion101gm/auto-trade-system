from app.config import settings
from app.infra.bybit_client import BybitClient
from app.strategy.indicators import calculate_atr, calculate_rsi
from .base_validator import BaseValidator, ValidationResult, ValidationStatus

# Thresholds from gold_opening_reversal.py
_ATR_HIGH = 45.0   # High volatility — reduce position size but still tradeable
_ATR_EXTREME = 80.0  # Extreme volatility — too dangerous for live entry
_RSI_OVERBOUGHT = 82.0
_RSI_OVERSOLD = 18.0
_FUNDING_EXTREME = 0.005  # 0.5% per 8h is extreme carry cost


class MarketRegimeValidator(BaseValidator):
    """
    Validate current XAUUSDT market conditions before going live.

    Checks that market data is fetchable and that the current regime
    (volatility, momentum, funding) is within acceptable bounds for
    live trading. A hostile regime does not BLOCK live trading but
    produces a WARNING so the operator can decide.
    """

    @property
    def layer_name(self) -> str:
        return "Market Regime"

    @property
    def weight(self) -> float:
        return 10

    async def validate(self) -> ValidationResult:
        checks = []
        passed = 0
        total = 4

        client = BybitClient(
            api_key=settings.BYBIT_API_KEY,
            api_secret=settings.BYBIT_API_SECRET,
            testnet=settings.BYBIT_USE_DEMO_DOMAIN,
        )

        try:
            # ----------------------------------------------------------------
            # Check 1: Live OHLCV data fetchable (minimum 20 candles required
            #           for ATR/RSI calculations with period=14)
            # ----------------------------------------------------------------
            try:
                ohlcv = await client.fetch_ohlcv(
                    settings.PRIMARY_TRADING_SYMBOL, timeframe='1h', limit=50
                )
            except Exception as e:
                return ValidationResult(
                    layer_name=self.layer_name,
                    status=ValidationStatus.ERROR,
                    score=0, checks_passed=0, checks_total=total,
                    errors=[f"OHLCV fetch failed: {e}"],
                )

            if not ohlcv or len(ohlcv) < 20:
                return ValidationResult(
                    layer_name=self.layer_name,
                    status=ValidationStatus.ERROR,
                    score=0, checks_passed=0, checks_total=total,
                    errors=[f"Insufficient candles: {len(ohlcv) if ohlcv else 0} (need ≥ 20)"],
                )

            passed += 1
            checks.append({'check': 'OHLCV Data', 'status': 'PASS',
                           'value': f"{len(ohlcv)} candles fetched"})

            # ----------------------------------------------------------------
            # Check 2: ATR volatility regime
            #   PASS  — ATR < 45  (normal)
            #   WARN  — 45 ≤ ATR < 80  (high — tradeable with reduced size)
            #   FAIL  — ATR ≥ 80  (extreme — too dangerous)
            # ----------------------------------------------------------------
            closes = [c[4] for c in ohlcv]
            try:
                atr = calculate_atr(ohlcv, period=14)
                if atr < _ATR_HIGH:
                    passed += 1
                    checks.append({'check': 'ATR Volatility', 'status': 'PASS',
                                   'value': f"{atr:.2f} (normal)"})
                elif atr < _ATR_EXTREME:
                    # High but tradeable — still pass for scoring but surface warning
                    passed += 1
                    checks.append({'check': 'ATR Volatility', 'status': 'WARNING',
                                   'value': f"{atr:.2f} (high — reduce position size)",
                                   'threshold': f"< {_ATR_HIGH}"})
                else:
                    checks.append({'check': 'ATR Volatility', 'status': 'FAIL',
                                   'value': f"{atr:.2f} (extreme)",
                                   'threshold': f"< {_ATR_EXTREME}"})
            except Exception as e:
                checks.append({'check': 'ATR Volatility', 'status': 'WARNING',
                               'note': f"Could not compute: {e}"})
                passed += 1  # Non-fatal — data might be on boundary

            # ----------------------------------------------------------------
            # Check 3: RSI momentum — extreme readings signal poor entry timing
            #   PASS  — 18 < RSI < 82  (no extreme momentum)
            #   WARN  — RSI ≤ 18 or ≥ 82  (extreme — high reversal risk)
            # ----------------------------------------------------------------
            try:
                rsi = calculate_rsi(closes, period=14)
                if _RSI_OVERSOLD < rsi < _RSI_OVERBOUGHT:
                    passed += 1
                    checks.append({'check': 'RSI Momentum', 'status': 'PASS',
                                   'value': f"RSI={rsi:.1f}"})
                else:
                    direction = "overbought" if rsi >= _RSI_OVERBOUGHT else "oversold"
                    # WARNING not FAIL — operator decides whether to wait
                    passed += 1
                    checks.append({'check': 'RSI Momentum', 'status': 'WARNING',
                                   'value': f"RSI={rsi:.1f} ({direction})",
                                   'note': 'Extreme momentum — consider waiting for reversion'})
            except Exception as e:
                checks.append({'check': 'RSI Momentum', 'status': 'WARNING',
                               'note': f"Could not compute: {e}"})
                passed += 1

            # ----------------------------------------------------------------
            # Check 4: Funding rate not extreme
            #   PASS  — |rate| < 0.5%
            #   WARN  — |rate| ≥ 0.5% (extreme carry cost or short squeeze)
            # ----------------------------------------------------------------
            try:
                funding_data = await client.fetch_funding_rate(
                    settings.PRIMARY_TRADING_SYMBOL, limit=1
                )
                if funding_data:
                    rate = float(funding_data[0].get('fundingRate', 0))
                    if abs(rate) < _FUNDING_EXTREME:
                        passed += 1
                        checks.append({'check': 'Funding Rate', 'status': 'PASS',
                                       'value': f"{rate:.4%}"})
                    else:
                        passed += 1
                        checks.append({'check': 'Funding Rate', 'status': 'WARNING',
                                       'value': f"{rate:.4%} (extreme carry cost)",
                                       'threshold': f"< {_FUNDING_EXTREME:.1%}"})
                else:
                    checks.append({'check': 'Funding Rate', 'status': 'SKIP',
                                   'note': 'No funding data returned'})
                    total -= 1
            except Exception as e:
                checks.append({'check': 'Funding Rate', 'status': 'SKIP',
                               'note': f"Not available: {e}"})
                total -= 1

        except Exception as e:
            return ValidationResult(
                layer_name=self.layer_name,
                status=ValidationStatus.ERROR,
                score=0, checks_passed=0, checks_total=total, errors=[str(e)],
            )
        finally:
            await client.close()

        score = (passed / total) * 100 if total > 0 else 0
        # Market regime is advisory — WARNING is acceptable for GO
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
