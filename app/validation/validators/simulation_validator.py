from app.paper_trading.session_manager import PaperTradingSessionManager
from app.config import settings
from .base_validator import BaseValidator, ValidationResult, ValidationStatus


class SimulationValidator(BaseValidator):

    @property
    def layer_name(self) -> str:
        return "Live Simulation"

    @property
    def weight(self) -> float:
        return 10

    async def validate(self) -> ValidationResult:
        checks = []
        passed = 0
        total = 2

        try:
            session_mgr = PaperTradingSessionManager(user_id="readiness_test")
            await session_mgr.start_session()

            # Check 1: Session started
            if session_mgr.session_active:
                passed += 1
                checks.append({'check': 'Session Started', 'status': 'PASS'})
            else:
                checks.append({'check': 'Session Started', 'status': 'FAIL'})

            # Check 2: Paper trade execution
            proposal = {
                'symbol': settings.PRIMARY_TRADING_SYMBOL,
                'side': 'BUY',
                'entry_price': 3300.0,  # Approximate XAUUSDT price
                'quantity': 0.01,
                'leverage': 2,
                'confidence': 0.8,
                'strategy_name': 'readiness_test',
            }
            result = await session_mgr.execute_paper_trade(proposal=proposal, exchange_client=None)
            if result.get('status') == 'executed':
                passed += 1
                checks.append({'check': 'Paper Trade Execution', 'status': 'PASS',
                                'latency_ms': result.get('latency_ms', 0)})
            else:
                checks.append({'check': 'Paper Trade Execution', 'status': 'FAIL',
                                'error': result.get('error')})

            await session_mgr.end_session()

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
