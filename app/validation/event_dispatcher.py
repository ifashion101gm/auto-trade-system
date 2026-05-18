"""
Event-driven validation dispatcher.

Subscribes to the system event_bus and runs targeted validators whenever
a trigger event fires — instead of waiting for the next scheduled
readiness check. This catches regime shifts the instant they happen.

Trigger map (from the enterprise architecture spec):

  Event                    → Validators
  ─────────────────────────────────────────────────────
  ORDER_REJECTED           → ExchangeValidator
  API_ERROR                → ExchangeValidator + InfrastructureValidator
  WEBSOCKET_DISCONNECTED   → ExchangeValidator
  WEBSOCKET_RECONNECTED    → ExchangeValidator
  RISK_VIOLATION_DETECTED  → RiskValidator + ExecutionQualityValidator
  SYNC_MISMATCH            → ExchangeValidator + RiskValidator
  POSITION_LIQUIDATED      → RiskValidator + MarketRegimeValidator
"""
import asyncio
import logging
from typing import Dict, List, Optional, Type

from app.events.event_types import (
    ORDER_REJECTED,
    API_ERROR,
    WEBSOCKET_DISCONNECTED,
    WEBSOCKET_RECONNECTED,
    RISK_VIOLATION_DETECTED,
    SYNC_MISMATCH,
    POSITION_LIQUIDATED,
)
from app.validation.validators.base_validator import BaseValidator, ValidationStatus

logger = logging.getLogger(__name__)

# Imported lazily inside _resolve_classes() to avoid circular imports at
# module load time (validators import settings which triggers config init).
_VALIDATOR_CLASS_NAMES: Dict[str, List[str]] = {
    ORDER_REJECTED:          ['ExchangeValidator'],
    API_ERROR:               ['ExchangeValidator', 'InfrastructureValidator'],
    WEBSOCKET_DISCONNECTED:  ['ExchangeValidator'],
    WEBSOCKET_RECONNECTED:   ['ExchangeValidator'],
    RISK_VIOLATION_DETECTED: ['RiskValidator', 'ExecutionQualityValidator'],
    SYNC_MISMATCH:           ['ExchangeValidator', 'RiskValidator'],
    POSITION_LIQUIDATED:     ['RiskValidator', 'MarketRegimeValidator'],
}


def _resolve_classes(names: List[str]) -> List[Type[BaseValidator]]:
    """Lazy import so config initialises only when a handler actually fires."""
    from app.validation.validators import (   # noqa: PLC0415
        ExchangeValidator,
        InfrastructureValidator,
        RiskValidator,
        ExecutionQualityValidator,
        MarketRegimeValidator,
    )
    mapping = {
        'ExchangeValidator':       ExchangeValidator,
        'InfrastructureValidator': InfrastructureValidator,
        'RiskValidator':           RiskValidator,
        'ExecutionQualityValidator': ExecutionQualityValidator,
        'MarketRegimeValidator':   MarketRegimeValidator,
    }
    return [mapping[n] for n in names if n in mapping]


class EventDrivenDispatcher:
    """
    Register once against the event_bus singleton; each trigger event
    runs the relevant validator(s) and logs or alerts on degradation.

    Usage (in app startup):
        from app.validation.event_dispatcher import dispatcher
        from app.events.event_bus import event_bus
        dispatcher.register(event_bus)
    """

    def __init__(self, persistence=None):
        # persistence: Optional[ReadinessPersistence] — injected to save results
        self._persistence = persistence
        self._registered = False
        self._in_flight: Dict[str, asyncio.Task] = {}   # deduplicate concurrent runs

    def register(self, event_bus, persistence=None) -> None:
        """
        Subscribe all trigger events to their handlers.
        Call once during application startup after event_bus is running.
        """
        if self._registered:
            return
        if persistence:
            self._persistence = persistence

        for event_type in _VALIDATOR_CLASS_NAMES:
            handler = self._make_handler(event_type)
            event_bus.subscribe(event_type, handler, priority=15)
            logger.debug("EventDrivenDispatcher registered for %s", event_type)

        self._registered = True
        logger.info("EventDrivenDispatcher active — monitoring %d event types",
                    len(_VALIDATOR_CLASS_NAMES))

    def _make_handler(self, event_type: str):
        async def handler(event: dict) -> None:
            await self._dispatch(event_type, event)
        return handler

    async def _dispatch(self, event_type: str, event: dict) -> None:
        """Run validators for this event, deduplicated against in-flight runs."""
        if event_type in self._in_flight and not self._in_flight[event_type].done():
            logger.debug("EventDrivenDispatcher: skipping %s — already in flight", event_type)
            return

        task = asyncio.create_task(self._run_validators(event_type, event))
        self._in_flight[event_type] = task

        try:
            await task
        except Exception as e:
            logger.error("EventDrivenDispatcher error for %s: %s", event_type, e)

    async def _run_validators(self, event_type: str, event: dict) -> None:
        classes = _resolve_classes(_VALIDATOR_CLASS_NAMES.get(event_type, []))
        if not classes:
            return

        symbol = event.get('payload', {}).get('symbol', 'XAUUSDT') if isinstance(event, dict) else 'XAUUSDT'
        logger.info("EventDrivenDispatcher: %s fired — running %s",
                    event_type, [c.__name__ for c in classes])

        failed_layers = []
        for cls in classes:
            try:
                result = await cls().validate()
                if result.status == ValidationStatus.FAIL:
                    failed_layers.append(result.layer_name)
                    logger.warning(
                        "⚠️  Event-triggered validation FAIL: [%s] score=%s/100 "
                        "triggered by %s",
                        result.layer_name, result.score, event_type,
                    )
                elif result.status == ValidationStatus.ERROR:
                    logger.error(
                        "❌ Event-triggered validation ERROR: [%s] %s",
                        result.layer_name, result.errors,
                    )
                else:
                    logger.info("✅ Event-triggered [%s] %s score=%s/100",
                                result.layer_name, result.status.value, result.score)

                if self._persistence:
                    from app.validation.readiness_scoring import ReadinessReport
                    mini_report = ReadinessReport(
                        overall_score=result.score,
                        status=result.status.value,
                        layer_results={result.layer_name: result},
                        recommendations=[],
                    )
                    self._persistence.save_from_report(
                        mini_report, mode='event', trigger=event_type
                    )

            except Exception as e:
                logger.error("EventDrivenDispatcher: validator %s raised: %s", cls.__name__, e)

        # If any targeted layer failed, send a Telegram alert
        if failed_layers:
            await self._alert(event_type, failed_layers)

    async def _alert(self, event_type: str, failed_layers: List[str]) -> None:
        try:
            from app.notifications.notifier import TelegramNotifier
            notifier = TelegramNotifier()
            if notifier.enabled:
                msg = (
                    f"⚠️ <b>Event-Triggered Validation Failed</b>\n"
                    f"Trigger: <code>{event_type}</code>\n"
                    f"Failed layers: {', '.join(failed_layers)}\n"
                    f"Action: check logs and consider halting trading"
                )
                await notifier.send_message(msg)
        except Exception as e:
            logger.error("EventDrivenDispatcher: alert failed: %s", e)


# Module-level singleton — import and call .register(event_bus) at startup
dispatcher = EventDrivenDispatcher()
