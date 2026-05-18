import time
from app.config import settings
from app.infra.bybit_client import BybitClient
from .base_validator import BaseValidator, ValidationResult, ValidationStatus


class ExchangeValidator(BaseValidator):

    @property
    def layer_name(self) -> str:
        return "Exchange Connectivity"

    @property
    def weight(self) -> float:
        return 15

    async def validate(self) -> ValidationResult:
        checks = []
        passed = 0
        total = 3

        # System exclusively trades XAUUSDT on Bybit
        client = BybitClient(
            api_key=settings.BYBIT_API_KEY,
            api_secret=settings.BYBIT_API_SECRET,
            testnet=True,
        )

        # Check 1: API connection + latency
        latency_ms = 9999.0
        try:
            start = time.time()
            balance = await client.fetch_balance()
            latency_ms = (time.time() - start) * 1000
            if balance:
                passed += 1
                checks.append({'check': 'API Connection', 'status': 'PASS', 'latency_ms': f"{latency_ms:.0f}ms"})
            else:
                checks.append({'check': 'API Connection', 'status': 'FAIL'})
        except Exception as e:
            checks.append({'check': 'API Connection', 'status': 'FAIL', 'error': str(e)})

        # Check 2: Latency under 3000ms
        if latency_ms < 3000:
            passed += 1
            checks.append({'check': 'API Latency', 'status': 'PASS', 'value': f"{latency_ms:.0f}ms"})
        else:
            checks.append({'check': 'API Latency', 'status': 'FAIL', 'value': f"{latency_ms:.0f}ms", 'threshold': '3000ms'})

        # Check 3: Primary symbol ticker available
        try:
            ticker = await client.fetch_ticker(settings.PRIMARY_TRADING_SYMBOL)
            if ticker:
                passed += 1
                checks.append({'check': f'Ticker {settings.PRIMARY_TRADING_SYMBOL}', 'status': 'PASS'})
            else:
                checks.append({'check': f'Ticker {settings.PRIMARY_TRADING_SYMBOL}', 'status': 'FAIL'})
        except Exception as e:
            checks.append({'check': f'Ticker {settings.PRIMARY_TRADING_SYMBOL}', 'status': 'FAIL', 'error': str(e)})

        score = (passed / total) * 100
        return ValidationResult(
            layer_name=self.layer_name,
            status=ValidationStatus.PASS if passed >= 2 else ValidationStatus.FAIL,
            score=score,
            checks_passed=passed,
            checks_total=total,
            details=checks,
        )
