"""
SmartOrderRouter — Multi-venue order routing with automatic failover.

C5 Architecture Decision:
  ENTRY orders  → primary only (Bybit). Never open positions on secondary —
                  unknown cross-venue margin exposure.
  CLOSE orders  → primary first; secondary only when primary circuit breaker
                  is OPEN or primary raises an exception.
  Read ops      → primary always; secondary not used for reads.

Phase 1 (current): Bybit primary + optional Binance secondary (CLOSE failover only)
Phase 2 (future):  True SOR with best-bid/offer routing across venues

Integration:
    router = SmartOrderRouter.build()               # from config
    router = SmartOrderRouter.build_with_secondary() # adds Binance fallback

    result = await router.create_market_order(symbol, side, amount, leverage,
                                              order_type=OrderType.CLOSE)
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from app.config import settings
from app.infra.exchange_manager import UnifiedExchangeManager
from app.logging_config import get_logger

logger = get_logger(__name__)


class OrderType(Enum):
    ENTRY = "entry"
    CLOSE = "close"


@dataclass
class RoutingResult:
    """Enriched order result carrying routing metadata."""
    raw: Dict[str, Any]
    venue: str
    failover: bool = False
    failover_reason: str = ""
    latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            **self.raw,
            "_routing": {
                "venue": self.venue,
                "failover": self.failover,
                "failover_reason": self.failover_reason,
                "latency_ms": round(self.latency_ms, 2),
            },
        }


class SmartOrderRouter:
    """
    Routes market orders across exchange venues with CLOSE-only failover.

    The router does NOT manage positions or track fills — that remains the
    responsibility of the execution layer and reconciliation engine.

    Failover trigger: primary circuit breaker state == 'OPEN' or primary
    raises any exception on a CLOSE order.
    """

    def __init__(
        self,
        primary: UnifiedExchangeManager,
        secondary: Optional[UnifiedExchangeManager] = None,
        circuit_breaker: Optional[Any] = None,
    ) -> None:
        self.primary = primary
        self.secondary = secondary
        self._circuit_breaker = circuit_breaker

        _primary_name = getattr(primary, "exchange_name", "primary")
        _secondary_name = getattr(secondary, "exchange_name", "none") if secondary else "none"
        logger.info(
            "✅ SmartOrderRouter ready — primary=%s secondary=%s failover=%s",
            _primary_name, _secondary_name, secondary is not None,
        )

    # ── Factory helpers ───────────────────────────────────────────────────────

    @classmethod
    def build(cls) -> "SmartOrderRouter":
        """Build router with Bybit primary only (no failover)."""
        from app.infra.circuit_breaker import get_circuit_breaker
        primary = UnifiedExchangeManager(
            exchange_name=settings.ACTIVE_EXCHANGE,
            use_testnet=settings.BINANCE_TESTNET,
        )
        return cls(primary=primary, circuit_breaker=get_circuit_breaker())

    @classmethod
    def build_with_secondary(cls) -> "SmartOrderRouter":
        """Build router with Bybit primary + Binance CLOSE-only failover."""
        from app.infra.circuit_breaker import get_circuit_breaker
        primary = UnifiedExchangeManager(
            exchange_name=settings.ACTIVE_EXCHANGE,
            use_testnet=settings.BINANCE_TESTNET,
        )
        # Only add secondary if Binance credentials are configured
        secondary: Optional[UnifiedExchangeManager] = None
        if settings.BINANCE_API_KEY and settings.BINANCE_API_SECRET:
            secondary = UnifiedExchangeManager(
                exchange_name="binance",
                use_testnet=settings.BINANCE_TESTNET,
            )
            logger.info("✅ Binance secondary venue configured for CLOSE failover")
        else:
            logger.warning(
                "⚠️  BINANCE_API_KEY not set — SmartOrderRouter running without secondary venue"
            )
        return cls(primary=primary, secondary=secondary, circuit_breaker=get_circuit_breaker())

    # ── Internal health check ─────────────────────────────────────────────────

    def _primary_healthy(self) -> bool:
        """True when primary circuit breaker is CLOSED or HALF_OPEN (not OPEN)."""
        if self._circuit_breaker is None:
            return True
        state = getattr(self._circuit_breaker, "state", "CLOSED")
        return state != "OPEN"

    # ── Order routing ─────────────────────────────────────────────────────────

    async def create_market_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        leverage: int = 1,
        order_type: OrderType = OrderType.ENTRY,
    ) -> Dict[str, Any]:
        """
        Route a market order with failover policy.

        ENTRY: primary only — raises on primary failure, no fallback.
        CLOSE: primary → secondary if primary is OPEN or raises.
        """
        t0 = time.monotonic()
        primary_name = getattr(self.primary, "exchange_name", "primary")

        if order_type == OrderType.ENTRY:
            # ENTRY: primary only — never open positions cross-venue
            logger.info("📤 ENTRY → %s %s %s qty=%s lev=%sx", primary_name, symbol, side, amount, leverage)
            raw = await self.primary.create_market_order(symbol, side, amount, leverage)
            return RoutingResult(
                raw=raw,
                venue=primary_name,
                latency_ms=(time.monotonic() - t0) * 1000,
            ).to_dict()

        # CLOSE: try primary first
        if self._primary_healthy():
            try:
                logger.info(
                    "📤 CLOSE → %s %s %s qty=%s lev=%sx",
                    primary_name, symbol, side, amount, leverage,
                )
                raw = await self.primary.create_market_order(symbol, side, amount, leverage)
                return RoutingResult(
                    raw=raw,
                    venue=primary_name,
                    latency_ms=(time.monotonic() - t0) * 1000,
                ).to_dict()
            except Exception as exc:
                reason = f"primary exception: {exc}"
                logger.error("❌ Primary CLOSE failed (%s) — attempting failover: %s", primary_name, exc)
        else:
            reason = f"primary circuit breaker OPEN ({primary_name})"
            logger.warning("⚠️  Primary circuit breaker OPEN — routing CLOSE to secondary")

        # Failover to secondary
        if self.secondary is None:
            raise RuntimeError(
                f"SmartOrderRouter: no secondary venue configured for CLOSE failover "
                f"({reason}). Cannot close {symbol}."
            )

        secondary_name = getattr(self.secondary, "exchange_name", "secondary")
        logger.warning(
            "🔀 FAILOVER: %s CLOSE → %s %s qty=%s [reason: %s]",
            symbol, secondary_name, side, amount, reason,
        )
        raw = await self.secondary.create_market_order(symbol, side, amount, leverage)
        return RoutingResult(
            raw=raw,
            venue=secondary_name,
            failover=True,
            failover_reason=reason,
            latency_ms=(time.monotonic() - t0) * 1000,
        ).to_dict()

    async def close_position(self, symbol: str) -> Dict[str, Any]:
        """Emergency full-position close with automatic failover."""
        t0 = time.monotonic()
        primary_name = getattr(self.primary, "exchange_name", "primary")

        if self._primary_healthy():
            try:
                raw = await self.primary.close_position(symbol)
                return RoutingResult(
                    raw=raw, venue=primary_name,
                    latency_ms=(time.monotonic() - t0) * 1000,
                ).to_dict()
            except Exception as exc:
                reason = f"primary exception: {exc}"
                logger.error("❌ Primary close_position failed: %s — failover", exc)
        else:
            reason = "primary circuit breaker OPEN"

        if self.secondary is None:
            raise RuntimeError(
                f"SmartOrderRouter: no secondary for emergency close_position "
                f"({symbol}). [{reason}]"
            )

        secondary_name = getattr(self.secondary, "exchange_name", "secondary")
        logger.critical(
            "🚨 EMERGENCY FAILOVER: close_position %s → %s [%s]",
            symbol, secondary_name, reason,
        )
        raw = await self.secondary.close_position(symbol)
        return RoutingResult(
            raw=raw, venue=secondary_name, failover=True,
            failover_reason=reason,
            latency_ms=(time.monotonic() - t0) * 1000,
        ).to_dict()

    # ── Read passthroughs (primary only — no failover needed) ─────────────────

    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        return await self.primary.fetch_ticker(symbol)

    async def fetch_ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 100) -> List:
        return await self.primary.fetch_ohlcv(symbol, timeframe, limit)

    async def fetch_balance(self) -> Dict[str, Any]:
        return await self.primary.fetch_balance()

    async def fetch_open_positions(self) -> List[Dict[str, Any]]:
        return await self.primary.fetch_open_positions()

    async def fetch_positions(self) -> List[Dict[str, Any]]:
        return await self.primary.fetch_positions()

    async def fetch_order_status(self, order_id: str, symbol: str) -> Dict[str, Any]:
        return await self.primary.fetch_order_status(order_id, symbol)

    async def cancel_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        return await self.primary.cancel_order(order_id, symbol)

    async def close(self) -> None:
        await self.primary.close()
        if self.secondary:
            await self.secondary.close()

    @property
    def info(self) -> Dict[str, Any]:
        return {
            "primary": getattr(self.primary, "exchange_name", "unknown"),
            "secondary": getattr(self.secondary, "exchange_name", "none") if self.secondary else None,
            "failover_enabled": self.secondary is not None,
            "primary_healthy": self._primary_healthy(),
        }
