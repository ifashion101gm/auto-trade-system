import subprocess
import psutil
from .base_validator import BaseValidator, ValidationResult, ValidationStatus


class InfrastructureValidator(BaseValidator):

    @property
    def layer_name(self) -> str:
        return "Infrastructure"

    @property
    def weight(self) -> float:
        return 15

    async def validate(self) -> ValidationResult:
        checks = []
        passed = 0
        total = 4

        # Check 1: CPU usage
        cpu_pct = psutil.cpu_percent(interval=1)
        if cpu_pct < 80:
            passed += 1
            checks.append({'check': 'CPU Usage', 'status': 'PASS', 'value': f"{cpu_pct:.1f}%"})
        else:
            checks.append({'check': 'CPU Usage', 'status': 'FAIL', 'value': f"{cpu_pct:.1f}%", 'threshold': '<80%'})

        # Check 2: RAM usage
        ram_pct = psutil.virtual_memory().percent
        if ram_pct < 85:
            passed += 1
            checks.append({'check': 'RAM Usage', 'status': 'PASS', 'value': f"{ram_pct:.1f}%"})
        else:
            checks.append({'check': 'RAM Usage', 'status': 'FAIL', 'value': f"{ram_pct:.1f}%", 'threshold': '<85%'})

        # Check 3: Disk space
        disk_pct = psutil.disk_usage('/').percent
        if disk_pct < 90:
            passed += 1
            checks.append({'check': 'Disk Space', 'status': 'PASS', 'value': f"{disk_pct:.1f}%"})
        else:
            checks.append({'check': 'Disk Space', 'status': 'FAIL', 'value': f"{disk_pct:.1f}%", 'threshold': '<90%'})

        # Check 4: PostgreSQL health
        try:
            result = subprocess.run(['pg_isready'], capture_output=True, timeout=5)
            if result.returncode == 0:
                passed += 1
                checks.append({'check': 'PostgreSQL', 'status': 'PASS'})
            else:
                checks.append({'check': 'PostgreSQL', 'status': 'FAIL'})
        except Exception:
            checks.append({'check': 'PostgreSQL', 'status': 'WARNING', 'note': 'pg_isready not found'})

        score = (passed / total) * 100
        return ValidationResult(
            layer_name=self.layer_name,
            status=ValidationStatus.PASS if passed >= 3 else ValidationStatus.FAIL,
            score=score,
            checks_passed=passed,
            checks_total=total,
            details=checks,
        )
