# 🏗️ Proposed Refactored Architecture

**Current State → Target State Transformation**  
**Aligned with:** [SELF_HEALING_ARCHITECTURE.md](./docs/SELF_HEALING_ARCHITECTURE.md)  

---

## Current Architecture (Before Refactoring)

```
┌─────────────────────────────────────────────────────────────┐
│                    LiveTradingService                        │
│                   (1,425 lines - GOD CLASS)                  │
│                                                               │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐ │
│  │ State Mgmt   │ │ Signal Gen   │ │ Order Execution      │ │
│  │ (lines       │ │ (lines       │ │ (lines               │ │
│  │  200-350)    │ │  450-500)    │ │  600-800)            │ │
│  └──────────────┘ └──────────────┘ └──────────────────────┘ │
│                                                               │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐ │
│  │ Monitoring   │ │ Reconcile    │ │ Learning &           │ │
│  │ (lines       │ │ (lines       │ │ Analytics            │ │
│  │  800-900)    │ │  1000-1100)  │ │ (lines 1100-1400)    │ │
│  └──────────────┘ └──────────────┘ └──────────────────────┘ │
│                                                               │
│  ❌ 12+ responsibilities in single class                     │
│  ❌ Impossible to unit test                                  │
│  ❌ Frequent merge conflicts                                 │
└─────────────────────────────────────────────────────────────┘
         ↓                    ↓                    ↓
┌────────────────┐ ┌────────────────┐ ┌────────────────────┐
│ RiskEngine     │ │ RiskManager    │ │ TradeValidator     │
│ (799 lines)    │ │ (484 lines)    │ │ (340 lines)        │
│                │ │                │ │                    │
│ ❌ Duplicate   │ │ ❌ Duplicate   │ │ ❌ Duplicate       │
│    logic       │ │    logic       │ │    logic           │
└────────────────┘ └────────────────┘ └────────────────────┘
         ↓                    ↓                    ↓
┌─────────────────────────────────────────────────────────────┐
│              Circular Dependencies                           │
│                                                               │
│  trading_service.py                                          │
│       ↓ imports                                               │
│  execution_service.py                                        │
│       ↓ imports                                               │
│  risk_engine.py                                              │
│       ↓ imports                                               │
│  exchange_manager.py                                         │
│       ↻ (potentially imports back to trading_service)        │
│                                                               │
│  ❌ Import errors at startup                                 │
│  ❌ Cannot test in isolation                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## Target Architecture (After Refactoring)

```
┌──────────────────────────────────────────────────────────────────┐
│                    Application Layer                              │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │              TradingOrchestrator (200 lines)                │  │
│  │   • Coordinates complete trading cycle                      │  │
│  │   • Thin orchestration layer                                │  │
│  │   • Delegates to specialized components                     │  │
│  └────────────────────────────────────────────────────────────┘  │
│           ↓              ↓              ↓              ↓          │
└──────────────────────────────────────────────────────────────────┘
           ↓              ↓              ↓              ↓
┌────────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────┐
│ StateMachine   │ │ Signal       │ │ Trade        │ │ Position │
│ Manager        │ │ Coordinator  │ │ Executor     │ │ Monitor  │
│ (80 lines)     │ │ (150 lines)  │ │ (180 lines)  │ │ Service  │
│                │ │              │ │              │ │(120 line)│
│ • State        │ │ • AI signal  │ │ • Order      │ │ • SL/TP  │
│   transitions  │ │   generation │ │   placement  │ │   enforce│
│ • Validation   │ │ • Risk       │ │ • Exchange   │ │ • Health │
│ • History      │ │   validation │ │   interaction│ │   checks │
└────────────────┘ └──────────────┘ └──────────────┘ └──────────┘
                                                   ↓
                                    ┌──────────────────────────┐
                                    │ Reconciliation           │
                                    │ Coordinator              │
                                    │ (100 lines)              │
                                    │                          │
                                    │ • DB-exchange sync       │
                                    │ • Orphan detection       │
                                    │ • Auto-repair            │
                                    └──────────────────────────┘


┌──────────────────────────────────────────────────────────────────┐
│                    Service Layer                                  │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │           ExecutionService (555 lines)                      │  │
│  │   • Centralized order lifecycle management                  │  │
│  │   • Idempotency protection                                  │  │
│  │   • Retry logic with exponential backoff                    │  │
│  │   • Circuit breaker integration                             │  │
│  └────────────────────────────────────────────────────────────┘  │
│           ↓                    ↓                    ↓             │
│  ┌────────────────┐ ┌──────────────┐ ┌──────────────────────┐   │
│  │ OrderRetry     │ │ Dedup        │ │ ExecutionAnomaly     │   │
│  │ Manager        │ │ Engine       │ │ Detector             │   │
│  │ (150 lines)    │ │ (280 lines)  │ │ (380 lines)          │   │
│  └────────────────┘ └──────────────┘ └──────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
           ↓                    ↓                    ↓
┌────────────────┐ ┌────────────────┐ ┌────────────────────────┐
│ UnifiedRisk    │ │ Exchange       │ │ Notification           │
│ Validator      │ │ Connector      │ │ Service                │
│ (300 lines)    │ │ (Interface)    │ │ (Interface)            │
│                │ │                │ │                        │
│ • Single       │ │ • Bybit        │ │ • Telegram             │
│   source of    │ │ • Binance      │ │ • Email (future)       │
│   truth for    │ │ • MEXC         │ │ • Webhook (future)     │
│   risk rules   │ │ • Pluggable    │ │ • Pluggable            │
└────────────────┘ └────────────────┘ └────────────────────────┘
           ↓
┌──────────────────────────────────────────────────────────────────┐
│                    Repository Layer                               │
│                                                                   │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐    │
│  │ Trade        │ │ User         │ │ Position             │    │
│  │ Repository   │ │ Repository   │ │ Repository           │    │
│  │ (200 lines)  │ │ (150 lines)  │ │ (180 lines)          │    │
│  │              │ │              │ │                      │    │
│  │ • get_today  │ │ • get_user   │ │ • get_open_positions │    │
│  │ • calc_pnl   │ │ • get_balance│ │ • update_position    │    │
│  │ • count_open │ │ • update_user│ │ • close_position     │    │
│  └──────────────┘ └──────────────┘ └──────────────────────┘    │
│           ↓                    ↓                    ↓             │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │              Database Abstraction (SQLAlchemy)              │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘


┌──────────────────────────────────────────────────────────────────┐
│                    Self-Healing Agents                            │
│  (Aligned with docs/SELF_HEALING_ARCHITECTURE.md)                 │
│                                                                   │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐    │
│  │ Signal       │ │ Order        │ │ Order Verification   │    │
│  │ Generation   │ │ Placement    │ │ Agent                │    │
│  │ Agent        │ │ Agent        │ │                      │    │
│  └──────────────┘ └──────────────┘ └──────────────────────┘    │
│           ↓                    ↓                    ↓             │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐    │
│  │ Health       │ │ Failure      │ │ Data Reconciliation  │    │
│  │ Monitoring   │ │ Recovery     │ │ Agent                │    │
│  │ Agent        │ │ Agent        │ │                      │    │
│  └──────────────┘ └──────────────┘ └──────────────────────┘    │
│           ↓                                                     │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │         SelfHealingExecutionEngine (664 lines)             │  │
│  │   • Coordinates all agents                                  │  │
│  │   • Pre-flight health gates                                 │  │
│  │   • Duplicate signal protection                             │  │
│  │   • Anomaly detection                                       │  │
│  │   • Verification-triggered recovery                         │  │
│  │   • Post-cycle reconciliation                               │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘


┌──────────────────────────────────────────────────────────────────┐
│                    Infrastructure Layer                           │
│                                                                   │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐    │
│  │ PostgreSQL   │ │ Redis        │ │ Message Queue        │    │
│  │              │ │              │ │ (future)             │    │
│  │ • Trades     │ │ • Cache      │ │ • Event bus          │    │
│  │ • Users      │ │ • Sessions   │ │ • Task queue         │    │
│  │ • Positions  │ │ • Rate limits│ │ • Dead letter queue  │    │
│  └──────────────┘ └──────────────┘ └──────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
```

---

## Dependency Flow (After Refactoring)

```
┌─────────────────────────────────────────────────────────────┐
│                     Dependency Graph                         │
│                     (No Cycles!)                             │
└─────────────────────────────────────────────────────────────┘

Application Layer
    ↓ depends on
Service Layer
    ↓ depends on
Repository Layer
    ↓ depends on
Infrastructure Layer

Self-Healing Agents
    ↓ depends on
Service Layer (via interfaces)

NO BACKWARD DEPENDENCIES! ✅
```

---

## Module Responsibilities

### Application Layer

#### TradingOrchestrator
**Responsibility:** Coordinate complete trading cycle  
**Lines:** ~200  
**Dependencies:** StateMachineManager, SignalCoordinator, TradeExecutor, PositionMonitor, ReconciliationCoordinator

**Key Methods:**
```python
async def execute_cycle(symbol, user_id, db_session, market_data)
async def get_current_state() -> ExecutionState
async def get_cycle_history() -> List[CycleRecord]
```

---

### Service Layer

#### ExecutionService
**Responsibility:** Centralized order lifecycle management  
**Lines:** ~555  
**Dependencies:** IRiskValidator (interface), IExchangeConnector (interface), database

**Key Methods:**
```python
async def execute_trade(request: ExecutionRequest, db_session) -> ExecutionResult
async def cancel_order(order_id: str, db_session) -> bool
async def verify_order(order_id: str) -> OrderStatus
```

#### UnifiedRiskValidator
**Responsibility:** Single source of truth for risk validation  
**Lines:** ~300  
**Dependencies:** Database (via repository), configuration

**Key Methods:**
```python
async def validate(proposal: TradeProposal, context: RiskContext) -> RiskDecision
async def _check_daily_loss_limit(...) -> RiskCheckResult
async def _check_drawdown_limit(...) -> RiskCheckResult
# ... 6 more check methods
```

---

### Repository Layer

#### TradeRepository
**Responsibility:** All trade-related database operations  
**Lines:** ~200  
**Dependencies:** SQLAlchemy session

**Key Methods:**
```python
async def get_today_trades(user_id: str) -> List[PaperTrade]
async def calculate_daily_pnl(user_id: str) -> float
async def count_open_positions(user_id: str) -> int
async def create_trade(trade_data: dict) -> PaperTrade
async def update_trade(trade_id: int, updates: dict) -> PaperTrade
```

---

### Self-Healing Agents

#### SignalGenerationAgent
**Responsibility:** Generate trading signals via AI  
**Lines:** ~120  
**Dependencies:** AIAgentOrchestrator, market data

#### OrderPlacementAgent
**Responsibility:** Place orders with retry logic  
**Lines:** ~150  
**Dependencies:** ExecutionService (delegates, doesn't duplicate)

#### OrderVerificationAgent
**Responsibility:** Verify orders exist on exchange  
**Lines:** ~130  
**Dependencies:** IExchangeConnector (interface)

#### HealthMonitoringAgent
**Responsibility:** Continuous system health tracking  
**Lines:** ~180  
**Dependencies:** CircuitBreaker, metrics collector

#### FailureRecoveryAgent
**Responsibility:** Automatic failure recovery  
**Lines:** ~200  
**Dependencies:** StartupRecoveryService, event bus

#### DataReconciliationAgent
**Responsibility:** Exchange-DB consistency checks  
**Lines:** ~160  
**Dependencies:** ReconciliationService, reconciliation engine

---

## Interface Definitions

### IRiskValidator
```python
class IRiskValidator(Protocol):
    async def validate(
        self,
        proposal: TradeProposal,
        context: RiskContext
    ) -> RiskDecision: ...
```

### IExchangeConnector
```python
class IExchangeConnector(Protocol):
    async def place_order(self, order_request: OrderRequest) -> OrderResult: ...
    async def get_positions(self) -> List[Position]: ...
    async def cancel_order(self, order_id: str) -> bool: ...
    async def get_order_status(self, order_id: str) -> OrderStatus: ...
```

### INotificationService
```python
class INotificationService(Protocol):
    async def send_alert(self, message: str, severity: str = "INFO") -> bool: ...
    async def send_trade_notification(self, trade_data: Dict[str, Any]) -> bool: ...
    async def send_health_alert(self, health_issue: HealthIssue) -> bool: ...
```

---

## Migration Strategy

### Phase 1: Parallel Implementation (Weeks 1-2)
```
Old Architecture          New Architecture
(LiveTradingService)      (Refactored Modules)
     │                          │
     │                          │
     ├──── Both Active ────────┤
     │   (Feature Flag)         │
     │                          │
     ↓                          ↓
  Production               Staging/Test
  (Old Code)              (New Code)
```

### Phase 2: Gradual Rollout (Weeks 3-4)
```
Week 3: 10% traffic → New Architecture
Week 4: 50% traffic → New Architecture
```

### Phase 3: Full Migration (Week 5)
```
Week 5: 100% traffic → New Architecture
       Deprecate old code
       Remove feature flag
```

### Phase 4: Cleanup (Week 6)
```
Week 6: Delete deprecated modules
       Update documentation
       Final validation
```

---

## Testing Strategy

### Unit Tests (Per Module)
```
tests/unit/
├── test_state_machine_manager.py      # 15 tests
├── test_signal_coordinator.py         # 12 tests
├── test_trade_executor.py             # 18 tests
├── test_position_monitor_service.py   # 10 tests
├── test_reconciliation_coordinator.py # 14 tests
├── test_unified_risk_validator.py     # 25 tests
├── test_trade_repository.py           # 20 tests
└── test_self_healing_agents/          # 30 tests
    ├── test_signal_generation_agent.py
    ├── test_order_placement_agent.py
    ├── test_order_verification_agent.py
    ├── test_health_monitoring_agent.py
    ├── test_failure_recovery_agent.py
    └── test_data_reconciliation_agent.py
```

**Total Unit Tests:** ~144 tests  
**Target Coverage:** >90%

---

### Integration Tests
```
tests/integration/
├── test_trading_orchestrator.py       # Full cycle tests
├── test_execution_service.py          # Order lifecycle tests
├── test_risk_validation.py            # End-to-end risk checks
├── test_repository_layer.py           # Database integration
└── test_self_healing_flow.py          # Agent coordination tests
```

**Total Integration Tests:** ~50 tests

---

## Performance Expectations

### Before Refactoring
- **Startup Time:** 30 seconds (lazy imports, circular dependency resolution)
- **API Latency (p95):** 350ms
- **Memory Usage:** 512 MB
- **Test Execution Time:** 45 seconds

### After Refactoring
- **Startup Time:** <10 seconds (no lazy imports, clean dependencies)
- **API Latency (p95):** <200ms (optimized queries, caching)
- **Memory Usage:** 384 MB (reduced duplication)
- **Test Execution Time:** 25 seconds (isolated unit tests)

**Improvements:**
- Startup: **67% faster**
- Latency: **43% lower**
- Memory: **25% reduction**
- Tests: **44% faster**

---

## Developer Experience Improvements

### Before Refactoring
```python
# Confusing imports
from app.execution.trading_service import LiveTradingService
from app.risk.risk_engine import RiskEngine
from app.risk.risk_manager import RiskManager  # Which one?!
from app.risk.validator import TradeValidator  # Or this one?!

# God class usage
service = LiveTradingService()
result = await service.execute_trading_cycle(...)  # 1,425 lines of mystery
```

### After Refactoring
```python
# Clear, focused imports
from app.execution.orchestrators.trading_orchestrator import TradingOrchestrator
from app.risk.unified_validator import UnifiedRiskValidator
from app.database.repositories.trade_repository import TradeRepository

# Composable components
orchestrator = TradingOrchestrator(
    state_manager=StateMachineManager(),
    signal_coordinator=SignalCoordinator(...),
    trade_executor=TradeExecutor(...),
)
result = await orchestrator.execute_cycle(...)  # Clear responsibility
```

---

## Summary

### Key Benefits of Refactored Architecture

1. **✅ Clear Separation of Concerns**
   - Each module has single responsibility
   - Easy to understand and modify
   - Minimal coupling between components

2. **✅ Testability**
   - All components independently testable
   - Mock interfaces for isolated testing
   - >90% code coverage achievable

3. **✅ Maintainability**
   - No god classes (<200 lines per module)
   - No circular dependencies
   - Consistent naming conventions

4. **✅ Extensibility**
   - Plug-and-play exchange connectors
   - Composable risk checks
   - Easy to add new agents

5. **✅ Performance**
   - Faster startup (no lazy imports)
   - Lower latency (optimized queries)
   - Reduced memory (less duplication)

6. **✅ Aligned with Self-Healing Architecture**
   - Agents coordinate via clear interfaces
   - Recovery flows well-defined
   - Monitoring integrated throughout

---

**Architecture Designed:** May 15, 2026  
**Implementation Timeline:** 10 weeks  
**Expected Completion:** July 24, 2026
