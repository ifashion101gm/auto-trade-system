from sqlalchemy import select
from app.database.connection import async_session_maker   # correct import
from app.database.models import PaperTrades              # correct import
from .base_validator import BaseValidator, ValidationResult, ValidationStatus


class StrategyValidator(BaseValidator):

    @property
    def layer_name(self) -> str:
        return "Strategy"

    @property
    def weight(self) -> float:
        return 20

    async def validate(self) -> ValidationResult:
        MIN_WIN_RATE = 45.0
        MIN_PROFIT_FACTOR = 1.5
        MAX_DRAWDOWN = 10.0

        try:
            async with async_session_maker() as db:
                result = await db.execute(
                    select(PaperTrades).where(PaperTrades.status == 'closed')
                )
                trades = result.scalars().all()

            if len(trades) < 10:
                return ValidationResult(
                    layer_name=self.layer_name,
                    status=ValidationStatus.WARNING,
                    score=50,
                    checks_passed=0,
                    checks_total=3,
                    warnings=[f"Insufficient trades: {len(trades)} (minimum: 10)"],
                )

            wins = sum(1 for t in trades if t.profit and t.profit > 0)
            win_rate = (wins / len(trades)) * 100

            gross_profit = sum(t.profit for t in trades if t.profit and t.profit > 0)
            gross_loss = abs(sum(t.profit for t in trades if t.profit and t.profit < 0))
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

            peak = balance = 100.0
            max_dd = 0.0
            for t in sorted(trades, key=lambda x: x.ts_close or ''):
                if t.profit:
                    balance += t.profit
                    peak = max(peak, balance)
                    max_dd = max(max_dd, (peak - balance) / peak * 100)

            checks = []
            passed = 0
            total = 3

            # Check 1: Win rate
            if win_rate >= MIN_WIN_RATE:
                passed += 1
                checks.append({'check': 'Win Rate', 'status': 'PASS', 'value': f"{win_rate:.2f}%"})
            else:
                checks.append({'check': 'Win Rate', 'status': 'FAIL', 'value': f"{win_rate:.2f}%", 'threshold': f"{MIN_WIN_RATE}%"})

            # Check 2: Profit factor
            if profit_factor >= MIN_PROFIT_FACTOR:
                passed += 1
                checks.append({'check': 'Profit Factor', 'status': 'PASS', 'value': f"{profit_factor:.2f}"})
            else:
                checks.append({'check': 'Profit Factor', 'status': 'FAIL', 'value': f"{profit_factor:.2f}", 'threshold': str(MIN_PROFIT_FACTOR)})

            # Check 3: Max drawdown
            if max_dd <= MAX_DRAWDOWN:
                passed += 1
                checks.append({'check': 'Max Drawdown', 'status': 'PASS', 'value': f"{max_dd:.2f}%"})
            else:
                checks.append({'check': 'Max Drawdown', 'status': 'FAIL', 'value': f"{max_dd:.2f}%", 'threshold': f"{MAX_DRAWDOWN}%"})

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
                score=0, checks_passed=0, checks_total=3, errors=[str(e)],
            )
