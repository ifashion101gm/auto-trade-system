from datetime import datetime, timedelta
from sqlalchemy import select, func
from app.database.connection import async_session_maker
from app.database.models import ExecutionLogs, Trades
from .base_validator import BaseValidator, ValidationResult, ValidationStatus

_LOOKBACK_HOURS = 48
_MIN_SAMPLE = 5           # Need at least this many logs to score quality
_SUCCESS_RATE_MIN = 0.90  # 90% of executions must succeed
_LATENCY_MAX_MS = 2000    # 2s ceiling for API round-trips
_RETRY_RATE_MAX = 0.20    # At most 20% of orders required a retry


class ExecutionQualityValidator(BaseValidator):
    """
    Audit historical execution quality from the ExecutionLogs table.

    Catches silent degradation: high retry rates, growing latency, or
    a cluster of ERROR-status trades that indicate exchange-side issues
    before they appear in P&L.
    """

    @property
    def layer_name(self) -> str:
        return "Execution Quality"

    @property
    def weight(self) -> float:
        return 10

    async def validate(self) -> ValidationResult:
        checks = []
        passed = 0
        total = 4

        since = datetime.utcnow() - timedelta(hours=_LOOKBACK_HOURS)

        try:
            async with async_session_maker() as db:
                # Pull execution logs from the last LOOKBACK_HOURS
                result = await db.execute(
                    select(ExecutionLogs).where(
                        ExecutionLogs.timestamp >= since
                    ).order_by(ExecutionLogs.timestamp.desc()).limit(200)
                )
                logs = result.scalars().all()

                # Pull trades currently in ERROR state
                err_result = await db.execute(
                    select(Trades).where(Trades.status == 'ERROR')
                )
                error_trades = err_result.scalars().all()

            # ----------------------------------------------------------------
            # Check 1: Enough execution history to evaluate quality
            # ----------------------------------------------------------------
            if len(logs) < _MIN_SAMPLE:
                # Insufficient history — not a failure, system may be new
                checks.append({'check': 'Execution History', 'status': 'WARNING',
                               'value': f"{len(logs)} records in last {_LOOKBACK_HOURS}h",
                               'note': f"Need ≥ {_MIN_SAMPLE} records to score quality"})
                # Can't score the remaining checks without data
                return ValidationResult(
                    layer_name=self.layer_name,
                    status=ValidationStatus.WARNING,
                    score=50,
                    checks_passed=0,
                    checks_total=total,
                    details=checks,
                    warnings=[f"Only {len(logs)} execution log records in last {_LOOKBACK_HOURS}h — "
                              f"run paper trading first to populate baseline metrics"],
                )

            passed += 1
            checks.append({'check': 'Execution History', 'status': 'PASS',
                           'value': f"{len(logs)} records in last {_LOOKBACK_HOURS}h"})

            # ----------------------------------------------------------------
            # Check 2: Success rate
            # ----------------------------------------------------------------
            success_count = sum(1 for l in logs if l.status == 'SUCCESS')
            success_rate = success_count / len(logs)
            if success_rate >= _SUCCESS_RATE_MIN:
                passed += 1
                checks.append({'check': 'Success Rate', 'status': 'PASS',
                               'value': f"{success_rate:.1%} ({success_count}/{len(logs)})"})
            else:
                checks.append({'check': 'Success Rate', 'status': 'FAIL',
                               'value': f"{success_rate:.1%} ({success_count}/{len(logs)})",
                               'threshold': f"≥ {_SUCCESS_RATE_MIN:.0%}"})

            # ----------------------------------------------------------------
            # Check 3: Average API latency
            # ----------------------------------------------------------------
            latencies = [l.latency_ms for l in logs if l.latency_ms is not None]
            if latencies:
                avg_latency = sum(latencies) / len(latencies)
                p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
                if avg_latency <= _LATENCY_MAX_MS:
                    passed += 1
                    checks.append({'check': 'API Latency', 'status': 'PASS',
                                   'value': f"avg={avg_latency:.0f}ms p95={p95_latency:.0f}ms"})
                else:
                    checks.append({'check': 'API Latency', 'status': 'FAIL',
                                   'value': f"avg={avg_latency:.0f}ms p95={p95_latency:.0f}ms",
                                   'threshold': f"avg ≤ {_LATENCY_MAX_MS}ms"})
            else:
                # No latency data recorded — warning, not fail
                passed += 1
                checks.append({'check': 'API Latency', 'status': 'WARNING',
                               'note': 'No latency data in execution logs'})

            # ----------------------------------------------------------------
            # Check 4: Retry rate
            # ----------------------------------------------------------------
            retry_count = sum(1 for l in logs if l.retry_count and l.retry_count > 0)
            retry_rate = retry_count / len(logs)
            if retry_rate <= _RETRY_RATE_MAX:
                passed += 1
                checks.append({'check': 'Retry Rate', 'status': 'PASS',
                               'value': f"{retry_rate:.1%} ({retry_count}/{len(logs)} orders retried)"})
            else:
                checks.append({'check': 'Retry Rate', 'status': 'FAIL',
                               'value': f"{retry_rate:.1%} ({retry_count}/{len(logs)} orders retried)",
                               'threshold': f"≤ {_RETRY_RATE_MAX:.0%}"})

            # ----------------------------------------------------------------
            # Bonus diagnostic: trades stuck in ERROR (not scored, just surfaced)
            # ----------------------------------------------------------------
            if error_trades:
                checks.append({'check': 'ERROR Trades', 'status': 'WARNING',
                               'value': f"{len(error_trades)} trade(s) in ERROR status",
                               'note': 'Run reconciliation to resolve'})

        except Exception as e:
            return ValidationResult(
                layer_name=self.layer_name,
                status=ValidationStatus.ERROR,
                score=0, checks_passed=0, checks_total=total, errors=[str(e)],
            )

        score = (passed / total) * 100
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
