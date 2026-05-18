# Production Readiness Validation System

## Overview

Create a production readiness validation command that runs automated pre-live trading checks across 11 layers and outputs a GO/NO-GO decision with weighted scoring.

**Primary Command**: `python scripts/system_readiness.py --mode quick`
**Alternative**: `make readiness-check`

---

## Architecture Design

### File Structure

```
scripts/
└── system_readiness.py              # Master orchestrator (NEW)

app/validation/                      # Directory already exists
├── __init__.py
├── readiness_scoring.py             # Weighted scoring engine (NEW)
└── validators/                      # Directory already exists
    ├── base_validator.py            # Abstract interface (NEW)
    ├── strategy_validator.py        # Layer 1 (NEW)
    ├── risk_validator.py            # Layer 2 (NEW)
    ├── exchange_validator.py        # Layer 3 (NEW)
    ├── ai_validator.py              # Layer 4 (NEW)
    ├── infra_validator.py           # Layer 5 (NEW)
    ├── monitoring_validator.py      # Layer 6 (NEW)
    ├── simulation_validator.py      # Layer 7 (NEW)
    ├── dashboard_validator.py       # Layer 8 (NEW)
    ├── market_regime_validator.py   # Layer 9  (BUILT ✓)
    ├── execution_quality_validator.py  # Layer 10 (BUILT ✓)
    └── deployment_integrity_validator.py  # Layer 11 (BUILT ✓)
```

> **Note**: Do NOT create the 7 standalone `scripts/validate_*.py` files listed in the original plan — they duplicate the module and add no value.

---

## Implementation Steps

### Step 1: Base Validator Interface

**File**: `app/validation/validators/base_validator.py`

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any
from enum import Enum


class ValidationStatus(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    ERROR = "ERROR"
    SKIP = "SKIP"


@dataclass
class ValidationResult:
    layer_name: str
    status: ValidationStatus
    score: float  # 0-100
    checks_passed: int
    checks_total: int
    details: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class BaseValidator(ABC):

    @abstractmethod
    async def validate(self) -> ValidationResult:
        pass

    @property
    @abstractmethod
    def layer_name(self) -> str:
        pass

    @property
    @abstractmethod
    def weight(self) -> float:
        pass
```

---

### Step 2: Scoring Engine

**File**: `app/validation/readiness_scoring.py`

```python
from dataclasses import dataclass
from typing import List, Dict
from .validators.base_validator import ValidationResult, ValidationStatus

# Weights must sum to 100 across all 11 validators
LAYER_WEIGHTS = {
    'Strategy':                20,
    'Risk Engine':             15,
    'Deployment Integrity':    15,
    'Exchange Connectivity':   10,
    'Execution Quality':       10,
    'Infrastructure':          10,
    'Market Regime':            5,
    'Live Simulation':          5,
    'Monitoring Systems':       5,
    'AI Agents':                3,
    'Dashboard API':            2,
}

READY_THRESHOLD = 85.0
PARTIAL_THRESHOLD = 70.0


@dataclass
class ReadinessReport:
    overall_score: float
    status: str  # "READY", "PARTIAL", "NOT_READY"
    layer_results: Dict[str, ValidationResult]
    recommendations: List[str]

    def is_ready(self) -> bool:
        critical_layers = {'Strategy', 'Risk Engine', 'Exchange Connectivity'}
        for name, result in self.layer_results.items():
            if name in critical_layers and result.status == ValidationStatus.FAIL:
                return False
        return self.overall_score >= READY_THRESHOLD


class ReadinessScorer:

    def calculate(self, results: List[ValidationResult]) -> ReadinessReport:
        total_score = 0.0
        for result in results:
            weight = LAYER_WEIGHTS.get(result.layer_name, 0)
            total_score += (result.score / 100.0) * weight

        if total_score >= READY_THRESHOLD:
            status = "READY"
        elif total_score >= PARTIAL_THRESHOLD:
            status = "PARTIAL"
        else:
            status = "NOT_READY"

        return ReadinessReport(
            overall_score=total_score,
            status=status,
            layer_results={r.layer_name: r for r in results},
            recommendations=self._generate_recommendations(results),
        )

    def _generate_recommendations(self, results: List[ValidationResult]) -> List[str]:
        recs = []
        for r in results:
            if r.status == ValidationStatus.FAIL:
                recs.append(f"[FAIL] {r.layer_name}: {r.checks_passed}/{r.checks_total} checks passed")
                for err in r.errors:
                    recs.append(f"  • {err}")
            elif r.status == ValidationStatus.WARNING:
                for w in r.warnings:
                    recs.append(f"[WARN] {r.layer_name}: {w}")
        return recs
```

> **Key fix**: `LAYER_WEIGHTS` uses exact `layer_name` strings matching each validator's `layer_name` property, and sums to 100. Critical layer FAIL blocks GO even if score ≥ 85.

---

### Step 3: Strategy Validator

**File**: `app/validation/validators/strategy_validator.py`

```python
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
```

> **Key fix**: `app.database.connection.async_session_maker` and `app.database.models.PaperTrades` (not `app.storage.*`). Counter uses fixed `total = 3`, no `total += 1` pattern.

---

### Step 4: Risk Engine Validator

**File**: `app/validation/validators/risk_validator.py`

```python
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
```

> **Key fixes**:
> - `CircuitBreaker` uses `.state` (CLOSED/OPEN/HALF_OPEN), not `.trading_disabled` / `.disable_reason`
> - `KillSwitch.is_engaged()` method exists; `.get_status().engaged_by` is actor, not `.reason`
> - Removed redundant "Risk Engine Initialized" check (instantiation success is already proven)

---

### Step 5: Exchange Connectivity Validator

**File**: `app/validation/validators/exchange_validator.py`

```python
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
```

> **Key fixes**:
> - Removed Binance branch — system is Bybit-only (`settings.ACTIVE_EXCHANGE = "bybit"`)
> - `latency_ms` initialized before try block to avoid `UnboundLocalError` when referenced in Check 2
> - Symbol changed from hardcoded `BTC/USDT` to `settings.PRIMARY_TRADING_SYMBOL` (XAUUSDT)
> - Latency threshold tightened to 3000ms (5000ms is too permissive for live trading)

---

### Step 6: AI Agents Validator

**File**: `app/validation/validators/ai_validator.py`

```python
from app.ai_agents.orchestrator import AIAgentOrchestrator
from .base_validator import BaseValidator, ValidationResult, ValidationStatus


class AIAgentValidator(BaseValidator):

    @property
    def layer_name(self) -> str:
        return "AI Agents"

    @property
    def weight(self) -> float:
        return 5

    async def validate(self) -> ValidationResult:
        checks = []
        passed = 0
        total = 2

        try:
            orchestrator = AIAgentOrchestrator(use_openrouter=True)

            # Check 1: Orchestrator initialized with LLM client
            if orchestrator.use_openrouter and orchestrator.llm_client:
                passed += 1
                checks.append({'check': 'LLM Client Configured', 'status': 'PASS'})
            else:
                checks.append({'check': 'LLM Client Configured', 'status': 'WARNING',
                                'note': 'No LLM client — AI analysis will be skipped'})

            # Check 2: API key present in config
            from app.config import settings
            if getattr(settings, 'OPENROUTER_API_KEY', None) or getattr(settings, 'ANTHROPIC_API_KEY', None):
                passed += 1
                checks.append({'check': 'AI API Key', 'status': 'PASS'})
            else:
                checks.append({'check': 'AI API Key', 'status': 'FAIL', 'note': 'No AI API key configured'})

            score = (passed / total) * 100
            # AI agents are non-critical; WARNING is acceptable
            status = ValidationStatus.PASS if passed == total else ValidationStatus.WARNING
            return ValidationResult(
                layer_name=self.layer_name,
                status=status,
                score=score,
                checks_passed=passed,
                checks_total=total,
                details=checks,
            )

        except Exception as e:
            return ValidationResult(
                layer_name=self.layer_name,
                status=ValidationStatus.WARNING,  # Non-critical layer
                score=0, checks_passed=0, checks_total=total, errors=[str(e)],
            )
```

> **Key fixes**:
> - Removed `_test_agent_connection()` call — this method does not exist on `AIAgentOrchestrator`
> - No live LLM API call in quick mode (expensive, slow, and not a "readiness" concern)
> - Errors downgraded to WARNING since AI agents are non-critical (weight: 5)
> - Fixed double-counting: `total` set once to 2, no `total += 1` increments

---

### Step 7: Infrastructure Validator

**File**: `app/validation/validators/infra_validator.py`

```python
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
```

> **Key fix**: Original plan initialized `total = 5` then did `total += 1` five times, making effective `total = 10`. Fixed to `total = 4` (removed Redis check — not a confirmed dependency; can be added later).

---

### Step 8: Monitoring Validator

**File**: `app/validation/validators/monitoring_validator.py`

```python
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
```

> **Key fixes**:
> - `CircuitBreaker.trading_disabled` → `.state == 'CLOSED'`
> - `WatchdogManager.check_all_health()` does not exist — replaced with import/instantiation check
> - Removed Prometheus check (server may not be running during readiness check)
> - `total = 3` fixed (original had `total = 4` then `total += 1` four times = 8)

---

### Step 9: Live Simulation Validator

**File**: `app/validation/validators/simulation_validator.py`

```python
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
```

> **Key fixes**: Symbol changed from `BTC/USDT` to `settings.PRIMARY_TRADING_SYMBOL`. Slippage check removed (paper mode has no real slippage). `total` fixed to 2.

---

### Step 9b: Dashboard API Validator

**File**: `app/validation/validators/dashboard_validator.py`

Functional test that the FastAPI dashboard is running and responding correctly. Tests public endpoints only; authenticated endpoints are attempted if `TRADING_API_SECRET` is configured.

```python
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
```

**What each check validates:**

| Check | Endpoint | Pass Condition |
|---|---|---|
| Health Endpoint | `GET /api/health` | HTTP 200, `status == "healthy"` (DB ping passed) |
| Readiness Endpoint | `GET /dashboard/readiness` | HTTP 200, response has `score` and `verdict` keys |
| Status Endpoint | `GET /dashboard/status` | HTTP 200, response has `trading_enabled` field |
| Trading Status (authed) | `GET /api/v1/trading/status` | HTTP 200 with `Authorization: Bearer {secret}` |

**Graceful degradations:**
- Server not running → returns `WARNING` (not `FAIL`) — it may be started separately before live trading begins
- `TRADING_API_SECRET` not set → Check 4 is `SKIP` and doesn't reduce the score
- Any single endpoint failure → `WARNING` if ≥50% pass, `FAIL` only if <50% pass

---

### Step 10: Master Orchestrator

**File**: `scripts/system_readiness.py`

```python
#!/usr/bin/env python3
import asyncio
import sys
import argparse
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.validation.readiness_scoring import ReadinessScorer
from app.validation.validators.strategy_validator import StrategyValidator
from app.validation.validators.risk_validator import RiskValidator
from app.validation.validators.exchange_validator import ExchangeValidator
from app.validation.validators.ai_validator import AIAgentValidator
from app.validation.validators.infra_validator import InfrastructureValidator
from app.validation.validators.monitoring_validator import MonitoringValidator
from app.validation.validators.simulation_validator import SimulationValidator
from app.validation.validators.dashboard_validator import DashboardValidator
from app.validation.validators.market_regime_validator import MarketRegimeValidator
from app.validation.validators.execution_quality_validator import ExecutionQualityValidator
from app.validation.validators.deployment_integrity_validator import DeploymentIntegrityValidator

STATUS_ICONS = {'PASS': '✅', 'FAIL': '❌', 'WARNING': '⚠️ ', 'ERROR': '🚨', 'SKIP': '➖'}


async def run_validators(mode: str = 'quick') -> 'ReadinessReport':
    print("=" * 70)
    print("PRODUCTION READINESS VALIDATION")
    print("=" * 70)
    print(f"Timestamp : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Mode      : {mode.upper()}")
    print("=" * 70)
    print()

    validators = [
        DeploymentIntegrityValidator(),   # Must be first — hard NO-GO on misconfig
        StrategyValidator(),
        RiskValidator(),
        ExchangeValidator(),
        ExecutionQualityValidator(),
        MarketRegimeValidator(),
        InfrastructureValidator(),
        MonitoringValidator(),
        AIAgentValidator(),
        DashboardValidator(),
        SimulationValidator(),
    ]

    if mode == 'quick':
        # Skip live simulation and market regime fetch in quick mode (<30s)
        skip = (SimulationValidator, MarketRegimeValidator)
        validators = [v for v in validators if not isinstance(v, skip)]

    results = []
    for validator in validators:
        print(f"[{validator.layer_name}]...")
        result = await validator.validate()
        results.append(result)
        icon = STATUS_ICONS.get(result.status.value, '?')
        print(f"  {icon} {result.status.value} — score {result.score:.0f}/100  "
              f"({result.checks_passed}/{result.checks_total} checks)")
        for err in result.errors:
            print(f"     ERROR: {err}")
        for w in result.warnings:
            print(f"     WARN : {w}")
        print()

    scorer = ReadinessScorer()
    report = scorer.calculate(results)

    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for name, r in report.layer_results.items():
        icon = STATUS_ICONS.get(r.status.value, '?')
        print(f"  {icon} {name:<28} {r.status.value:<8} {r.score:.0f}/100")

    print()
    print(f"  Overall Score : {report.overall_score:.1f}/100")
    print()

    if report.is_ready():
        print("  ✅ GO — READY FOR LIMITED LIVE TRADING")
        print("     Recommended: 0.25% risk/trade, 2% daily max loss, ≤3 positions")
    else:
        print("  ❌ NO-GO — RESOLVE ISSUES BEFORE LIVE TRADING")
        for rec in report.recommendations:
            print(f"     {rec}")

    print("=" * 70)
    return report


def main():
    parser = argparse.ArgumentParser(description='Production Readiness Validation')
    parser.add_argument('--mode', choices=['quick', 'deep'], default='quick',
                        help='quick=no live sim (<30s)  deep=all layers (5-10min)')
    args = parser.parse_args()
    report = asyncio.run(run_validators(mode=args.mode))
    sys.exit(0 if report.is_ready() else 1)


if __name__ == '__main__':
    main()
```

---

### Step 11: Makefile Targets

**File**: `Makefile` (append)

```makefile
readiness-check: ## Run quick production readiness validation (<30s)
	$(VENV_PYTHON) scripts/system_readiness.py --mode quick; \
	EXIT=$$?; \
	if [ $$EXIT -eq 0 ]; then echo "✅ GO"; else echo "❌ NO-GO"; fi; \
	exit $$EXIT

readiness-deep: ## Run full readiness validation including live simulation
	$(VENV_PYTHON) scripts/system_readiness.py --mode deep; \
	EXIT=$$?; \
	if [ $$EXIT -eq 0 ]; then echo "✅ GO"; else echo "❌ NO-GO"; fi; \
	exit $$EXIT
```

> **Key fix**: Original Makefile used `if [ $$? -eq 0 ]` after the Python call completed, but `$$?` captures the `if` statement's own exit code. Save to `EXIT` variable first.

---

## Configuration Thresholds

Add to `app/config.py`:

```python
# Readiness Validation
READINESS_MIN_WIN_RATE: float = 45.0
READINESS_MIN_PROFIT_FACTOR: float = 1.5
READINESS_MAX_DRAWDOWN: float = 10.0
READINESS_MAX_API_LATENCY_MS: float = 3000.0
READINESS_MIN_OVERALL_SCORE: float = 85.0
```

---

## Testing

```bash
# Quick smoke test
python scripts/system_readiness.py --mode quick

# Deep test (includes live paper trade simulation)
python scripts/system_readiness.py --mode deep
```

Unit tests in `tests/unit/test_validation/` — mock DB and exchange calls; assert score and status for known inputs.

---

## Deliverables

1. `app/validation/validators/base_validator.py` **(BUILT ✓)**
2. `app/validation/readiness_scoring.py`
3. `app/validation/validators/` — 11 validator modules
   - `market_regime_validator.py` **(BUILT ✓)**
   - `execution_quality_validator.py` **(BUILT ✓)**
   - `deployment_integrity_validator.py` **(BUILT ✓)**
   - remaining 8 validators (Lingma implements from plan)
4. `scripts/system_readiness.py`
5. Makefile targets
6. Config thresholds in `app/config.py`

---

## Success Criteria

- Quick mode completes in <30s (no live LLM calls, no paper trade sim)
- Deep mode completes in <5 min
- Exit code 0 = GO, 1 = NO-GO (CI/CD compatible)
- Critical layer FAIL (Strategy / Risk Engine / Exchange / Deployment Integrity) always blocks GO
- Dashboard server not running → `WARNING` only (server may be started after readiness check passes)
- Market Regime: ATR extreme → FAIL; ATR high or RSI extreme → WARNING (advisory, not blocking)
- Execution Quality: insufficient history → WARNING with score=50 (system may be freshly provisioned)
- Deployment Integrity: any FAIL = hard NO-GO regardless of overall score

---

## Bug Index (fixes applied vs original plan)

| # | Original Bug | Fix Applied |
|---|---|---|
| 1 | `app.storage.models` / `app.storage.db` | `app.database.models` / `app.database.connection` |
| 2 | `CircuitBreaker.trading_disabled` / `.disable_reason` | `.state == 'CLOSED'` (actual attribute) |
| 3 | `KillSwitch.get_status().reason` | `.is_engaged()` + `.get_status().engaged_by` |
| 4 | `AIAgentOrchestrator._test_agent_connection()` | Does not exist — replaced with config check |
| 5 | `total = N` + `total += 1` × N → double count | Fixed `total` constant per validator |
| 6 | `LAYER_WEIGHTS` key mismatch (`execution`, missing layers) | Keys match exact `layer_name` strings; sum = 100 |
| 7 | `latency_ms` used outside try scope | Initialized before try block |
| 8 | Hardcoded `BTC/USDT` | `settings.PRIMARY_TRADING_SYMBOL` (XAUUSDT) |
| 9 | Makefile `$$?` captures wrong exit | Saved to `EXIT` variable before conditional |
| 10 | `WatchdogManager.check_all_health()` called | Method doesn't exist — import/instantiation check only |
| 11 | `_generate_recommendations()` called but not implemented | Implemented in scoring engine |
| 12 | 7 redundant `scripts/validate_*.py` files in file structure | Removed — not needed |
