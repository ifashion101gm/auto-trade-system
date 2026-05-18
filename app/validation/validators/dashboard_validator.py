import httpx
from app.config import settings
from .base_validator import BaseValidator, ValidationResult, ValidationStatus

DASHBOARD_BASE = "http://localhost:8000"


class DashboardValidator(BaseValidator):

    @property
    def layer_name(self) -> str:
        return "Dashboard API"

    @property
    def weight(self) -> float:
        return 5

    async def validate(self) -> ValidationResult:
        checks = []
        passed = 0
        total = 4

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:

                # Check 1: Server reachable
                try:
                    resp = await client.get(f"{DASHBOARD_BASE}/api/health")
                    if resp.status_code == 200:
                        body = resp.json()
                        if body.get("status") == "healthy":
                            passed += 1
                            checks.append({'check': 'Health Endpoint', 'status': 'PASS',
                                           'value': 'healthy'})
                        else:
                            checks.append({'check': 'Health Endpoint', 'status': 'FAIL',
                                           'value': body.get("status", "unknown")})
                    else:
                        checks.append({'check': 'Health Endpoint', 'status': 'FAIL',
                                       'value': f"HTTP {resp.status_code}"})
                except httpx.ConnectError:
                    # Server not running — remaining checks are skipped
                    checks.append({'check': 'Health Endpoint', 'status': 'WARNING',
                                   'note': 'Dashboard server not running on :8000'})
                    return ValidationResult(
                        layer_name=self.layer_name,
                        status=ValidationStatus.WARNING,
                        score=0,
                        checks_passed=0,
                        checks_total=total,
                        warnings=['Dashboard server not running — start with `make start` or `uvicorn app.main:app`'],
                    )

                # Check 2: Readiness summary endpoint
                try:
                    resp = await client.get(f"{DASHBOARD_BASE}/dashboard/readiness")
                    if resp.status_code == 200:
                        body = resp.json()
                        score = body.get("score", -1)
                        verdict = body.get("verdict", "unknown")
                        passed += 1
                        checks.append({'check': 'Readiness Endpoint', 'status': 'PASS',
                                       'value': f"score={score} verdict={verdict}"})
                    else:
                        checks.append({'check': 'Readiness Endpoint', 'status': 'FAIL',
                                       'value': f"HTTP {resp.status_code}"})
                except Exception as e:
                    checks.append({'check': 'Readiness Endpoint', 'status': 'FAIL', 'error': str(e)})

                # Check 3: System status snapshot
                try:
                    resp = await client.get(f"{DASHBOARD_BASE}/dashboard/status")
                    if resp.status_code == 200:
                        body = resp.json()
                        trading_enabled = body.get("trading_enabled")
                        passed += 1
                        checks.append({'check': 'Status Endpoint', 'status': 'PASS',
                                       'value': f"trading_enabled={trading_enabled}"})
                    else:
                        checks.append({'check': 'Status Endpoint', 'status': 'FAIL',
                                       'value': f"HTTP {resp.status_code}"})
                except Exception as e:
                    checks.append({'check': 'Status Endpoint', 'status': 'FAIL', 'error': str(e)})

                # Check 4: Authenticated trading status (skip gracefully if secret not set)
                secret = getattr(settings, 'TRADING_API_SECRET', None)
                if secret:
                    try:
                        resp = await client.get(
                            f"{DASHBOARD_BASE}/api/v1/trading/status",
                            headers={"Authorization": f"Bearer {secret}"},
                        )
                        if resp.status_code == 200:
                            passed += 1
                            checks.append({'check': 'Trading Status (authed)', 'status': 'PASS'})
                        else:
                            checks.append({'check': 'Trading Status (authed)', 'status': 'FAIL',
                                           'value': f"HTTP {resp.status_code}"})
                    except Exception as e:
                        checks.append({'check': 'Trading Status (authed)', 'status': 'FAIL', 'error': str(e)})
                else:
                    # Secret not configured — don't penalise
                    total -= 1
                    checks.append({'check': 'Trading Status (authed)', 'status': 'SKIP',
                                   'note': 'TRADING_API_SECRET not set'})

        except Exception as e:
            return ValidationResult(
                layer_name=self.layer_name,
                status=ValidationStatus.ERROR,
                score=0, checks_passed=0, checks_total=total, errors=[str(e)],
            )

        score = (passed / total) * 100 if total > 0 else 0
        return ValidationResult(
            layer_name=self.layer_name,
            status=ValidationStatus.PASS if passed == total else (
                ValidationStatus.WARNING if passed >= total * 0.5 else ValidationStatus.FAIL
            ),
            score=score,
            checks_passed=passed,
            checks_total=total,
            details=checks,
        )
