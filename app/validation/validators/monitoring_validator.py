import httpx
from app.notifications.notifier import TelegramNotifier
from app.infra.circuit_breaker import CircuitBreaker
from .base_validator import BaseValidator, ValidationResult, ValidationStatus


class MonitoringValidator(BaseValidator):

    @property
    def layer_name(self) -> str:
        return "Monitoring Systems"

    @property
    def weight(self) -> float:
        return 10

    async def validate(self) -> ValidationResult:
        checks = []
        passed = 0
        total = 3

        # Check 1: Telegram notifier configured
        notifier = TelegramNotifier()
        if notifier.enabled:
            passed += 1
            checks.append({'check': 'Telegram Configured', 'status': 'PASS'})
        else:
            checks.append({'check': 'Telegram Configured', 'status': 'WARNING', 'note': 'Not configured'})

        # Check 2: Circuit breaker in CLOSED state
        # CircuitBreaker.state is 'CLOSED' | 'OPEN' | 'HALF_OPEN' — no trading_disabled attribute
        cb = CircuitBreaker()
        if cb.state == 'CLOSED':
            passed += 1
            checks.append({'check': 'Circuit Breaker CLOSED', 'status': 'PASS'})
        else:
            checks.append({'check': 'Circuit Breaker CLOSED', 'status': 'FAIL', 'value': cb.state})

        # Check 3: Self-healing watchdogs module importable
        try:
            from app.self_healing.watchdogs import WatchdogManager
            # WatchdogManager has no check_all_health(); verify it loads cleanly
            WatchdogManager()
            passed += 1
            checks.append({'check': 'Self-Healing Module', 'status': 'PASS'})
        except Exception as e:
            checks.append({'check': 'Self-Healing Module', 'status': 'WARNING', 'note': str(e)})

        score = (passed / total) * 100
        return ValidationResult(
            layer_name=self.layer_name,
            status=ValidationStatus.PASS if passed >= 2 else ValidationStatus.FAIL,
            score=score,
            checks_passed=passed,
            checks_total=total,
            details=checks,
        )
