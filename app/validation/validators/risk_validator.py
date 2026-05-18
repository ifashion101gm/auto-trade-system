from app.risk.risk_engine import RiskEngine
from app.infra.circuit_breaker import CircuitBreaker
from app.infra.kill_switch import KillSwitch
from .base_validator import BaseValidator, ValidationResult, ValidationStatus


class RiskValidator(BaseValidator):

    @property
    def layer_name(self) -> str:
        return "Risk Engine"

    @property
    def weight(self) -> float:
        return 20

    async def validate(self) -> ValidationResult:
        checks = []
        passed = 0
        total = 5

        try:
            risk_engine = RiskEngine()  # db_session optional

            # Check 1: Daily loss limit configured
            if risk_engine.max_daily_loss_pct > 0:
                passed += 1
                checks.append({'check': 'Daily Loss Limit', 'status': 'PASS', 'value': f"{risk_engine.max_daily_loss_pct:.1%}"})
            else:
                checks.append({'check': 'Daily Loss Limit', 'status': 'FAIL'})

            # Check 2: Drawdown limit configured
            if risk_engine.max_drawdown_pct > 0:
                passed += 1
                checks.append({'check': 'Max Drawdown Limit', 'status': 'PASS', 'value': f"{risk_engine.max_drawdown_pct:.1%}"})
            else:
                checks.append({'check': 'Max Drawdown Limit', 'status': 'FAIL'})

            # Check 3: Position size cap configured
            if risk_engine.max_position_size_pct > 0:
                passed += 1
                checks.append({'check': 'Position Size Cap', 'status': 'PASS', 'value': f"{risk_engine.max_position_size_pct:.1%}"})
            else:
                checks.append({'check': 'Position Size Cap', 'status': 'FAIL'})

            # Check 4: Kill switch disengaged
            # KillSwitch.is_engaged() is the correct method; get_status().engaged_by is actor, not reason
            kill_switch = KillSwitch()
            if not kill_switch.is_engaged():
                passed += 1
                checks.append({'check': 'Kill Switch Disengaged', 'status': 'PASS'})
            else:
                ks_status = kill_switch.get_status()
                checks.append({'check': 'Kill Switch', 'status': 'FAIL', 'reason': f"Engaged by: {ks_status.engaged_by}"})

            # Check 5: Circuit breaker not tripped
            # CircuitBreaker uses .state = 'CLOSED' | 'OPEN' | 'HALF_OPEN' — no trading_disabled attribute
            cb = CircuitBreaker()
            if cb.state == 'CLOSED':
                passed += 1
                checks.append({'check': 'Circuit Breaker', 'status': 'PASS', 'value': cb.state})
            else:
                checks.append({'check': 'Circuit Breaker', 'status': 'FAIL', 'value': cb.state})

            score = (passed / total) * 100
            return ValidationResult(
                layer_name=self.layer_name,
                status=ValidationStatus.PASS if passed == total else ValidationStatus.FAIL,
                score=score,
                checks_passed=passed,
                checks_total=total,
                details=checks,
            )

        except Exception as e:
            return ValidationResult(
                layer_name=self.layer_name,
                status=ValidationStatus.ERROR,
                score=0, checks_passed=0, checks_total=total, errors=[str(e)],
            )
