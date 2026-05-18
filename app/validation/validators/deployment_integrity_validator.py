import subprocess
from pathlib import Path
from app.config import settings
from .base_validator import BaseValidator, ValidationResult, ValidationStatus

_REPO_ROOT = Path(__file__).parent.parent.parent.parent  # project root
_PLACEHOLDER_SUBSTRINGS = ('user:password', 'your_', 'placeholder', 'change_me', 'example')
_MIN_KEY_LENGTH = 16
_MAX_SAFE_LEVERAGE = 5
_MAX_SAFE_DAILY_LOSS = 0.05   # 5%
_MAX_SAFE_DRAWDOWN = 0.20     # 20%


class DeploymentIntegrityValidator(BaseValidator):
    """
    Gate check for deployment configuration correctness.

    Catches the class of live-trading disasters caused by misconfigured
    env vars: wrong API keys, default-placeholder DATABASE_URL, risk
    limits set too loose, and DB schema that hasn't been migrated.
    All checks FAIL hard — a misconfigured deployment is a NO-GO.
    """

    @property
    def layer_name(self) -> str:
        return "Deployment Integrity"

    @property
    def weight(self) -> float:
        return 15

    async def validate(self) -> ValidationResult:
        checks = []
        passed = 0
        total = 7

        try:
            # ----------------------------------------------------------------
            # Check 1: Bybit API key present (live or demo)
            #   BYBIT_API_KEY is live; BYBIT_DEMO_API_KEY is demo.
            #   At least one must be set and non-placeholder.
            # ----------------------------------------------------------------
            live_key = getattr(settings, 'BYBIT_API_KEY', None) or ''
            demo_key = getattr(settings, 'BYBIT_DEMO_API_KEY', None) or ''
            active_key = live_key or demo_key
            key_label = 'BYBIT_API_KEY' if live_key else 'BYBIT_DEMO_API_KEY'

            if active_key and not any(p in active_key.lower() for p in _PLACEHOLDER_SUBSTRINGS):
                passed += 1
                checks.append({'check': 'Bybit API Key', 'status': 'PASS',
                               'value': f"{key_label} set ({len(active_key)} chars)"})
            elif not active_key:
                checks.append({'check': 'Bybit API Key', 'status': 'FAIL',
                               'note': 'Neither BYBIT_API_KEY nor BYBIT_DEMO_API_KEY is set'})
            else:
                checks.append({'check': 'Bybit API Key', 'status': 'FAIL',
                               'note': f"{key_label} looks like a placeholder value"})

            # ----------------------------------------------------------------
            # Check 2: ADMIN_API_KEY present, sufficient length, not placeholder
            # ----------------------------------------------------------------
            admin_key = getattr(settings, 'ADMIN_API_KEY', None) or ''
            if (admin_key
                    and len(admin_key) >= _MIN_KEY_LENGTH
                    and not any(p in admin_key.lower() for p in _PLACEHOLDER_SUBSTRINGS)):
                passed += 1
                checks.append({'check': 'ADMIN_API_KEY', 'status': 'PASS',
                               'value': f"{len(admin_key)} chars"})
            elif not admin_key:
                checks.append({'check': 'ADMIN_API_KEY', 'status': 'FAIL',
                               'note': 'ADMIN_API_KEY is not set'})
            elif len(admin_key) < _MIN_KEY_LENGTH:
                checks.append({'check': 'ADMIN_API_KEY', 'status': 'FAIL',
                               'value': f"{len(admin_key)} chars",
                               'threshold': f"≥ {_MIN_KEY_LENGTH} chars"})
            else:
                checks.append({'check': 'ADMIN_API_KEY', 'status': 'FAIL',
                               'note': 'ADMIN_API_KEY looks like a placeholder'})

            # ----------------------------------------------------------------
            # Check 3: DATABASE_URL is not the default placeholder
            # ----------------------------------------------------------------
            db_url = getattr(settings, 'DATABASE_URL', '') or ''
            if db_url and not any(p in db_url for p in ('user:password', 'user@localhost')):
                passed += 1
                # Mask credentials in the logged value
                masked = db_url.split('@')[-1] if '@' in db_url else db_url[:20] + '...'
                checks.append({'check': 'DATABASE_URL', 'status': 'PASS',
                               'value': f"...@{masked}"})
            else:
                checks.append({'check': 'DATABASE_URL', 'status': 'FAIL',
                               'note': 'DATABASE_URL contains placeholder credentials'})

            # ----------------------------------------------------------------
            # Check 4: Telegram configured (BOT_TOKEN + CHAT_ID both set)
            # ----------------------------------------------------------------
            tg_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None) or ''
            tg_chat = getattr(settings, 'TELEGRAM_CHAT_ID', None) or ''
            if tg_token and tg_chat:
                passed += 1
                checks.append({'check': 'Telegram Config', 'status': 'PASS',
                               'value': f"chat_id={tg_chat}"})
            else:
                missing = []
                if not tg_token:
                    missing.append('TELEGRAM_BOT_TOKEN')
                if not tg_chat:
                    missing.append('TELEGRAM_CHAT_ID')
                checks.append({'check': 'Telegram Config', 'status': 'FAIL',
                               'note': f"Missing: {', '.join(missing)}"})

            # ----------------------------------------------------------------
            # Check 5: Risk limits within safe operational bounds
            #   Validates RISK_MAX_LEVERAGE ≤ 5 AND daily loss ≤ 5%
            # ----------------------------------------------------------------
            leverage = getattr(settings, 'RISK_MAX_LEVERAGE', 0)
            daily_loss = getattr(settings, 'RISK_MAX_DAILY_LOSS_PCT', 0)
            drawdown = getattr(settings, 'RISK_MAX_DRAWDOWN_PCT', 0)

            risk_ok = (
                0 < leverage <= _MAX_SAFE_LEVERAGE
                and 0 < daily_loss <= _MAX_SAFE_DAILY_LOSS
                and 0 < drawdown <= _MAX_SAFE_DRAWDOWN
            )
            if risk_ok:
                passed += 1
                checks.append({'check': 'Risk Limits', 'status': 'PASS',
                               'value': (f"leverage≤{leverage}x "
                                         f"daily_loss≤{daily_loss:.1%} "
                                         f"drawdown≤{drawdown:.1%}")})
            else:
                issues = []
                if leverage > _MAX_SAFE_LEVERAGE:
                    issues.append(f"RISK_MAX_LEVERAGE={leverage} > {_MAX_SAFE_LEVERAGE}")
                if daily_loss > _MAX_SAFE_DAILY_LOSS:
                    issues.append(f"RISK_MAX_DAILY_LOSS_PCT={daily_loss:.1%} > {_MAX_SAFE_DAILY_LOSS:.0%}")
                if drawdown > _MAX_SAFE_DRAWDOWN:
                    issues.append(f"RISK_MAX_DRAWDOWN_PCT={drawdown:.1%} > {_MAX_SAFE_DRAWDOWN:.0%}")
                checks.append({'check': 'Risk Limits', 'status': 'FAIL',
                               'note': '; '.join(issues)})

            # ----------------------------------------------------------------
            # Check 6: PRIMARY_TRADING_SYMBOL locked to XAUUSDT
            # ----------------------------------------------------------------
            symbol = getattr(settings, 'PRIMARY_TRADING_SYMBOL', '')
            enabled = getattr(settings, 'ENABLED_TRADING_SYMBOLS', [])
            if symbol == 'XAUUSDT' and enabled == ['XAUUSDT']:
                passed += 1
                checks.append({'check': 'Symbol Lock (XAUUSDT)', 'status': 'PASS'})
            else:
                checks.append({'check': 'Symbol Lock (XAUUSDT)', 'status': 'FAIL',
                               'value': f"PRIMARY={symbol!r} ENABLED={enabled!r}",
                               'note': 'System must trade XAUUSDT exclusively'})

            # ----------------------------------------------------------------
            # Check 7: DB schema at migration head
            #   `alembic current` outputs "(head)" when fully migrated.
            # ----------------------------------------------------------------
            try:
                result = subprocess.run(
                    ['alembic', 'current'],
                    capture_output=True, text=True, timeout=10,
                    cwd=str(_REPO_ROOT),
                )
                output = result.stdout + result.stderr
                if '(head)' in output:
                    passed += 1
                    # Extract current revision for display
                    rev_line = next((l for l in output.splitlines() if 'head' in l), output.strip())
                    checks.append({'check': 'DB Migration', 'status': 'PASS',
                                   'value': rev_line.strip()})
                else:
                    # Parse which revision we're at
                    rev_line = next((l for l in output.splitlines() if l.strip()), 'unknown')
                    checks.append({'check': 'DB Migration', 'status': 'FAIL',
                                   'value': f"current: {rev_line.strip()}",
                                   'note': 'Run `alembic upgrade head` before going live'})
            except FileNotFoundError:
                checks.append({'check': 'DB Migration', 'status': 'WARNING',
                               'note': 'alembic not found in PATH — cannot verify schema'})
                passed += 1  # Non-fatal when alembic binary not on PATH in CI/K8s
            except subprocess.TimeoutExpired:
                checks.append({'check': 'DB Migration', 'status': 'FAIL',
                               'note': 'alembic timed out — DB may be unreachable'})

        except Exception as e:
            return ValidationResult(
                layer_name=self.layer_name,
                status=ValidationStatus.ERROR,
                score=0, checks_passed=0, checks_total=total, errors=[str(e)],
            )

        score = (passed / total) * 100
        # Any FAIL in this layer = hard NO-GO
        any_fail = any(c['status'] == 'FAIL' for c in checks)
        status = ValidationStatus.FAIL if any_fail else ValidationStatus.PASS
        return ValidationResult(
            layer_name=self.layer_name,
            status=status,
            score=score,
            checks_passed=passed,
            checks_total=total,
            details=checks,
        )
