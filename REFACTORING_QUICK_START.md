# 🚀 Critical Refactoring Quick Start Guide

**For:** Developers implementing P0 refactoring tasks  
**Time to Complete:** 2 weeks (80 hours)  
**Prerequisites:** Read [CODE_REFACTORING_AUDIT_REPORT.md](./CODE_REFACTORING_AUDIT_REPORT.md) first  

---

## Quick Navigation

- [Task C1: Split LiveTradingService](#task-c1-split-livetradingervice-god-class)
- [Task C2: Consolidate Risk Validation](#task-c2-consolidate-risk-validation-logic)
- [Task C3: Break Circular Dependencies](#task-c3-break-circular-dependencies)

---

## Task C1: Split LiveTradingService God Class

### Why This Matters
- **Current State:** 1,425-line file with 12+ responsibilities
- **Problem:** Impossible to test, hard to understand, merge conflicts frequent
- **Goal:** 6 focused modules, each <200 lines

### Before You Start
```bash
# 1. Create backup branch
git checkout -b refactor/split-trading-service

# 2. Run existing tests (must pass before refactoring)
pytest tests/ -v --tb=short

# 3. Measure current complexity
radon cc app/execution/trading_service.py -s

# 4. Document current API (for backward compatibility)
grep -n "async def" app/execution/trading_service.py > /tmp/current_api.txt
```

### Step-by-Step Implementation

#### Step 1: Extract State Machine Manager (Day 2)

**Create new file:** `app/execution/orchestrators/state_machine_manager.py`

```python
"""State machine manager for trading lifecycle."""
from datetime import datetime
from typing import List, Tuple
from app.execution.states import ExecutionState, is_valid_transition


class StateTransition:
    """Records a state transition event."""
    def __init__(self, from_state: ExecutionState, to_state: ExecutionState, timestamp: datetime):
        self.from_state = from_state
        self.to_state = to_state
        self.timestamp = timestamp


class StateMachineManager:
    """Manages execution state transitions with validation and history."""
    
    def __init__(self, initial_state: ExecutionState = ExecutionState.IDLE):
        self.current_state = initial_state
        self.history: List[StateTransition] = []
    
    def transition_to(self, new_state: ExecutionState) -> bool:
        """
        Attempt state transition with validation.
        
        Args:
            new_state: Target state
            
        Returns:
            True if transition successful
            
        Raises:
            InvalidStateTransition: If transition is not allowed
        """
        if not is_valid_transition(self.current_state, new_state):
            raise InvalidStateTransition(
                f"Cannot transition from {self.current_state} to {new_state}"
            )
        
        # Record transition
        transition = StateTransition(
            from_state=self.current_state,
            to_state=new_state,
            timestamp=datetime.utcnow()
        )
        self.history.append(transition)
        self.current_state = new_state
        
        return True
    
    def get_history(self) -> List[StateTransition]:
        """Get full state transition history."""
        return self.history.copy()
    
    def reset(self):
        """Reset state machine to IDLE."""
        self.transition_to(ExecutionState.IDLE)


class InvalidStateTransition(Exception):
    """Raised when invalid state transition is attempted."""
    pass
```

**Update trading_service.py:**
```python
# Add import at top
from app.execution.orchestrators.state_machine_manager import StateMachineManager

# In __init__ method, replace:
# OLD:
self.current_state = ExecutionState.IDLE
self.state_history: List[Tuple[ExecutionState, datetime]] = []

# NEW:
self.state_manager = StateMachineManager(initial_state=ExecutionState.IDLE)

# Replace all state transitions:
# OLD:
if not is_valid_transition(self.current_state, ExecutionState.FETCHING_DATA):
    ...
self.current_state = ExecutionState.FETCHING_DATA

# NEW:
try:
    self.state_manager.transition_to(ExecutionState.FETCHING_DATA)
except InvalidStateTransition as e:
    logger.error(f"Invalid state transition: {e}")
    return {'status': 'invalid_state'}
```

**Test it:**
```bash
pytest tests/unit/test_state_machine_manager.py -v
```

---

#### Step 2: Extract Signal Coordinator (Day 3)

**Create new file:** `app/execution/coordinators/signal_coordinator.py`

```python
"""Signal generation and validation coordinator."""
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_agents.orchestrator import AIAgentOrchestrator
from app.risk.risk_engine import RiskEngine
from app.risk.validator import TradeValidator
from app.logging_config import get_logger

logger = get_logger(__name__)


class SignalCoordinator:
    """Coordinates signal generation and risk validation."""
    
    def __init__(
        self,
        orchestrator: AIAgentOrchestrator,
        risk_engine: RiskEngine,
        validator: TradeValidator
    ):
        self.orchestrator = orchestrator
        self.risk_engine = risk_engine
        self.validator = validator
    
    async def generate_and_validate_signal(
        self,
        symbol: str,
        user_id: str,
        db_session: AsyncSession,
        market_data: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Generate trading signal and validate against risk rules.
        
        Args:
            symbol: Trading symbol
            user_id: User identifier
            db_session: Database session
            market_data: Pre-fetched market data (optional)
            
        Returns:
            Validated signal proposal or None if no signal/rejected
        """
        # Step 1: Generate signal via AI orchestrator
        logger.info(f"Generating signal for {symbol}")
        signal = await self.orchestrator.analyze_symbol(
            symbol=symbol,
            market_data=market_data
        )
        
        if not signal:
            logger.info(f"No signal generated for {symbol}")
            return None
        
        # Step 2: Validate against risk engine
        logger.info(f"Validating signal risk for {symbol}")
        risk_decision = await self.risk_engine.check_trade_approval(
            proposal=signal,
            user_id=user_id,
            db_session=db_session
        )
        
        if not risk_decision.get('approved', False):
            violations = risk_decision.get('violations', [])
            logger.warning(f"Signal rejected for {symbol}: {violations}")
            return None
        
        # Step 3: Additional validation via TradeValidator
        validation_result = await self.validator.validate_trade(
            proposal=signal,
            user_id=user_id,
            db_session=db_session,
            symbol=symbol
        )
        
        if not validation_result.approved:
            logger.warning(f"Validation failed for {symbol}: {validation_result.violations}")
            return None
        
        logger.info(f"Signal approved for {symbol}: {signal.get('side')}")
        return signal
```

**Update trading_service.py:**
```python
# In __init__, add:
from app.execution.coordinators.signal_coordinator import SignalCoordinator

self.signal_coordinator = SignalCoordinator(
    orchestrator=self.orchestrator,
    risk_engine=self.risk_engine,
    validator=self.validator
)

# In execute_trading_cycle, replace signal generation code with:
signal = await self.signal_coordinator.generate_and_validate_signal(
    symbol=symbol,
    user_id=user_id,
    db_session=db_session,
    market_data=market_data
)

if not signal:
    return {'status': 'no_signal_or_rejected'}
```

---

#### Step 3: Extract Trade Executor (Day 4)

**Create new file:** `app/execution/services/trade_executor.py`

```python
"""Trade execution service wrapper."""
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.execution.execution_service import ExecutionService, ExecutionRequest
from app.logging_config import get_logger

logger = get_logger(__name__)


class TradeExecutor:
    """Executes trades via centralized ExecutionService."""
    
    def __init__(self, execution_service: ExecutionService):
        self.execution_service = execution_service
    
    async def execute_trade(
        self,
        signal: Dict[str, Any],
        user_id: str,
        db_session: AsyncSession
    ) -> Dict[str, Any]:
        """
        Execute trade based on validated signal.
        
        Args:
            signal: Validated signal proposal
            user_id: User identifier
            db_session: Database session
            
        Returns:
            Execution result dictionary
        """
        # Build execution request from signal
        request = ExecutionRequest(
            symbol=signal.get('symbol'),
            side=signal.get('side'),
            entry_price=signal.get('entry_price'),
            quantity=signal.get('quantity'),
            leverage=signal.get('leverage', 1),
            stop_loss=signal.get('stop_loss'),
            take_profit=signal.get('take_profit'),
            strategy_name=signal.get('strategy_name'),
            confidence=signal.get('confidence'),
            user_id=user_id,
            execution_mode='fully-auto'
        )
        
        logger.info(f"Executing trade: {request.side} {request.quantity} {request.symbol}")
        
        # Execute via centralized service
        result = await self.execution_service.execute_trade(
            request=request,
            db_session=db_session
        )
        
        if result.success:
            logger.info(f"Trade executed successfully: order_id={result.order_id}")
        else:
            logger.error(f"Trade execution failed: {result.error}")
        
        return result.to_dict()
```

**Update trading_service.py:**
```python
# In __init__, add:
from app.execution.services.trade_executor import TradeExecutor

self.trade_executor = TradeExecutor(execution_service=self.execution_service)

# In execute_trading_cycle, replace execution code with:
execution_result = await self.trade_executor.execute_trade(
    signal=signal,
    user_id=user_id,
    db_session=db_session
)

if not execution_result.get('success'):
    return {'status': 'execution_failed', 'error': execution_result.get('error')}
```

---

#### Step 4: Create Thin Orchestrator (Day 7)

**Create new file:** `app/execution/orchestrators/trading_orchestrator.py`

```python
"""Trading cycle orchestrator - coordinates all components."""
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.execution.orchestrators.state_machine_manager import StateMachineManager
from app.execution.coordinators.signal_coordinator import SignalCoordinator
from app.execution.services.trade_executor import TradeExecutor
from app.execution.states import ExecutionState
from app.logging_config import get_logger

logger = get_logger(__name__)


class TradingOrchestrator:
    """Orchestrates complete trading cycle using specialized components."""
    
    def __init__(
        self,
        state_manager: StateMachineManager,
        signal_coordinator: SignalCoordinator,
        trade_executor: TradeExecutor,
        # Add other coordinators/services as extracted
    ):
        self.state_manager = state_manager
        self.signal_coordinator = signal_coordinator
        self.trade_executor = trade_executor
    
    async def execute_cycle(
        self,
        symbol: str,
        user_id: str,
        db_session: AsyncSession,
        market_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute complete trading cycle.
        
        Args:
            symbol: Trading symbol
            user_id: User identifier
            db_session: Database session
            market_data: Market data for analysis
            
        Returns:
            Cycle result dictionary
        """
        try:
            # Transition to FETCHING_DATA
            self.state_manager.transition_to(ExecutionState.FETCHING_DATA)
            
            # Transition to ANALYZING
            self.state_manager.transition_to(ExecutionState.ANALYZING)
            
            # Generate and validate signal
            signal = await self.signal_coordinator.generate_and_validate_signal(
                symbol=symbol,
                user_id=user_id,
                db_session=db_session,
                market_data=market_data
            )
            
            if not signal:
                self.state_manager.transition_to(ExecutionState.IDLE)
                return {'status': 'no_signal'}
            
            # Transition to EXECUTING
            self.state_manager.transition_to(ExecutionState.EXECUTING)
            
            # Execute trade
            execution_result = await self.trade_executor.execute_trade(
                signal=signal,
                user_id=user_id,
                db_session=db_session
            )
            
            if not execution_result.get('success'):
                self.state_manager.transition_to(ExecutionState.IDLE)
                return {'status': 'execution_failed', 'result': execution_result}
            
            # Transition to MONITORING
            self.state_manager.transition_to(ExecutionState.MONITORING)
            
            # TODO: Add position monitoring, reconciliation, etc.
            
            # Transition back to IDLE
            self.state_manager.transition_to(ExecutionState.IDLE)
            
            return {
                'status': 'cycle_complete',
                'execution_result': execution_result
            }
        
        except Exception as e:
            logger.error(f"Trading cycle failed: {e}", exc_info=True)
            # Reset to IDLE on error
            self.state_manager.reset()
            return {'status': 'error', 'error': str(e)}
```

**Update trading_service.py to use orchestrator:**
```python
# In __init__, add:
from app.execution.orchestrators.trading_orchestrator import TradingOrchestrator

self.trading_orchestrator = TradingOrchestrator(
    state_manager=self.state_manager,
    signal_coordinator=self.signal_coordinator,
    trade_executor=self.trade_executor,
    # Add other components
)

# Replace execute_trading_cycle with thin wrapper:
async def execute_trading_cycle(self, symbol: str, user_id: str, db_session):
    """Execute trading cycle via orchestrator (backward compatible)."""
    # Fetch market data
    market_data = await self._fetch_market_data(symbol)
    
    # Delegate to orchestrator
    return await self.trading_orchestrator.execute_cycle(
        symbol=symbol,
        user_id=user_id,
        db_session=db_session,
        market_data=market_data
    )
```

---

### Validation Checklist

After completing all steps:

- [ ] `trading_service.py` is <300 lines
- [ ] Each new module is <200 lines
- [ ] All unit tests passing: `pytest tests/unit/ -v`
- [ ] All integration tests passing: `pytest tests/integration/ -v`
- [ ] No regression in manual testing
- [ ] Code review completed
- [ ] Documentation updated

---

## Task C2: Consolidate Risk Validation Logic

### Why This Matters
- **Current State:** 3 duplicate validators with inconsistent logic
- **Problem:** Bug fixes must be applied 3 times, different enforcement paths
- **Goal:** Single `UnifiedRiskValidator` class

### Implementation Steps

#### Step 1: Create Unified Validator Skeleton

**Create file:** `app/risk/unified_validator.py`

```python
"""Unified risk validator - single source of truth for all risk checks."""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class RiskContext:
    """Context for risk validation."""
    user_id: str
    db_session: AsyncSession
    account_balance: float = 100.0  # Default starting balance


@dataclass
class RiskDecision:
    """Decision from risk validation."""
    approved: bool
    violations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'approved': self.approved,
            'violations': self.violations,
            'warnings': self.warnings,
            **self.metadata
        }


class UnifiedRiskValidator:
    """
    Single source of truth for all risk validations.
    
    Replaces:
    - RiskEngine.check_trade_approval()
    - RiskManager.validate_trade()
    - TradeValidator.validate_trade()
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize with configuration.
        
        Args:
            config: Risk thresholds (uses defaults from settings if not provided)
        """
        from app.config import settings
        
        self.config = config or {
            'max_daily_loss_pct': settings.RISK_MAX_DAILY_LOSS_PCT,
            'max_drawdown_pct': settings.RISK_MAX_DRAWDOWN_PCT,
            'max_position_size_pct': settings.RISK_MAX_POSITION_SIZE_PCT,
            'max_leverage': settings.RISK_MAX_LEVERAGE,
            'max_consecutive_losses': settings.RISK_MAX_CONSECUTIVE_LOSSES,
            'cooldown_period_seconds': settings.RISK_COOLDOWN_PERIOD_SECONDS,
        }
        
        # Runtime state
        self.daily_pnl = 0.0
        self.peak_balance = 100.0
        self.consecutive_losses = 0
    
    async def validate(
        self,
        proposal: Dict[str, Any],
        context: RiskContext
    ) -> RiskDecision:
        """
        Run all risk checks in priority order.
        
        Args:
            proposal: Trade proposal from signal generator
            context: Validation context with user info and DB session
            
        Returns:
            RiskDecision with approval status
        """
        violations = []
        warnings = []
        
        # Check 1: Emergency stop
        emergency_check = await self._check_emergency_stop(context)
        if not emergency_check.approved:
            return emergency_check
        
        # Check 2: Daily loss limit
        daily_loss_check = await self._check_daily_loss_limit(proposal, context)
        if not daily_loss_check.approved:
            violations.extend(daily_loss_check.violations)
        
        # Check 3: Drawdown limit
        drawdown_check = await self._check_drawdown_limit(context)
        if not drawdown_check.approved:
            violations.extend(drawdown_check.violations)
        
        # Check 4: Position size
        position_check = await self._check_position_size(proposal, context)
        if not position_check.approved:
            violations.extend(position_check.violations)
        
        # Check 5: Leverage limit
        leverage_check = await self._check_leverage_limit(proposal)
        if not leverage_check.approved:
            violations.extend(leverage_check.violations)
        
        # Check 6: Consecutive losses
        consecutive_check = await self._check_consecutive_losses(context)
        if not consecutive_check.approved:
            violations.extend(consecutive_check.violations)
        
        # Compile decision
        approved = len(violations) == 0
        
        return RiskDecision(
            approved=approved,
            violations=violations,
            warnings=warnings,
            metadata={
                'checks_performed': 6,
                'daily_pnl': self.daily_pnl,
                'consecutive_losses': self.consecutive_losses,
            }
        )
    
    async def _check_emergency_stop(self, context: RiskContext) -> RiskDecision:
        """Check if emergency stop is active."""
        # TODO: Implement emergency stop check
        return RiskDecision(approved=True)
    
    async def _check_daily_loss_limit(
        self,
        proposal: Dict[str, Any],
        context: RiskContext
    ) -> RiskDecision:
        """Check if daily loss limit would be exceeded."""
        # Calculate daily P&L
        daily_pnl = await self._calculate_daily_pnl(context.user_id, context.db_session)
        
        if abs(daily_pnl) > self.config['max_daily_loss_pct']:
            return RiskDecision(
                approved=False,
                violations=[f'Daily loss limit exceeded: {daily_pnl:.2f}%']
            )
        
        return RiskDecision(approved=True)
    
    async def _check_drawdown_limit(self, context: RiskContext) -> RiskDecision:
        """Check if drawdown limit exceeded."""
        # Calculate current drawdown
        drawdown = ((self.peak_balance - context.account_balance) / self.peak_balance) * 100
        
        if drawdown > self.config['max_drawdown_pct']:
            return RiskDecision(
                approved=False,
                violations=[f'Drawdown limit exceeded: {drawdown:.2f}%']
            )
        
        return RiskDecision(approved=True)
    
    async def _check_position_size(
        self,
        proposal: Dict[str, Any],
        context: RiskContext
    ) -> RiskDecision:
        """Check if position size within limits."""
        entry_price = proposal.get('entry_price', 0)
        quantity = proposal.get('quantity', 0)
        leverage = proposal.get('leverage', 1)
        
        position_value = entry_price * quantity * leverage
        position_pct = (position_value / context.account_balance) * 100
        
        if position_pct > self.config['max_position_size_pct']:
            return RiskDecision(
                approved=False,
                violations=[f'Position size too large: {position_pct:.2f}%']
            )
        
        return RiskDecision(approved=True)
    
    async def _check_leverage_limit(self, proposal: Dict[str, Any]) -> RiskDecision:
        """Check if leverage within limits."""
        leverage = proposal.get('leverage', 1)
        
        if leverage > self.config['max_leverage']:
            return RiskDecision(
                approved=False,
                violations=[f'Leverage too high: {leverage}x (max {self.config["max_leverage"]}x)']
            )
        
        return RiskDecision(approved=True)
    
    async def _check_consecutive_losses(self, context: RiskContext) -> RiskDecision:
        """Check if consecutive loss limit reached."""
        if self.consecutive_losses >= self.config['max_consecutive_losses']:
            return RiskDecision(
                approved=False,
                violations=[f'Max consecutive losses reached: {self.consecutive_losses}']
            )
        
        return RiskDecision(approved=True)
    
    async def _calculate_daily_pnl(self, user_id: str, db_session: AsyncSession) -> float:
        """Calculate daily P&L percentage."""
        from sqlalchemy import select, func
        from app.database.models import PaperTrades
        from datetime import datetime
        
        # Get today's trades
        stmt = select(PaperTrades).where(
            PaperTrades.user_id == user_id,
            func.date(PaperTrades.timestamp) == datetime.utcnow().date()
        )
        result = await db_session.execute(stmt)
        trades = result.scalars().all()
        
        # Calculate P&L
        daily_pnl = sum(t.pnl_usd for t in trades if t.status == 'closed')
        daily_pnl_pct = (daily_pnl / 100.0) * 100  # Assuming $100 starting balance
        
        return daily_pnl_pct
```

---

#### Step 2: Create Legacy Adapters

**Create file:** `app/risk/adapters.py`

```python
"""Legacy adapters for gradual migration to unified validator."""
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.risk.unified_validator import UnifiedRiskValidator, RiskContext, RiskDecision


class LegacyRiskEngineAdapter:
    """Adapts UnifiedRiskValidator to old RiskEngine API."""
    
    def __init__(self, unified_validator: UnifiedRiskValidator):
        self.validator = unified_validator
    
    async def check_trade_approval(
        self,
        proposal: Dict[str, Any],
        user_id: str,
        db_session: AsyncSession
    ) -> Dict[str, Any]:
        """Old API signature, delegates to new validator."""
        context = RiskContext(user_id=user_id, db_session=db_session)
        decision = await self.validator.validate(proposal, context)
        
        # Convert to old format
        return {
            'approved': decision.approved,
            'violations': decision.violations,
            'warnings': decision.warnings,
            **decision.metadata
        }


class LegacyRiskManagerAdapter:
    """Adapts UnifiedRiskValidator to old RiskManager API."""
    
    def __init__(self, unified_validator: UnifiedRiskValidator):
        self.validator = unified_validator
    
    async def validate_trade(
        self,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
        leverage: int,
        user_id: str,
        db_session: AsyncSession
    ) -> Dict[str, Any]:
        """Old API signature, delegates to new validator."""
        # Build proposal from parameters
        proposal = {
            'symbol': symbol,
            'side': side,
            'quantity': quantity,
            'entry_price': entry_price,
            'leverage': leverage,
        }
        
        context = RiskContext(user_id=user_id, db_session=db_session)
        decision = await self.validator.validate(proposal, context)
        
        return decision.to_dict()


class LegacyTradeValidatorAdapter:
    """Adapts UnifiedRiskValidator to old TradeValidator API."""
    
    def __init__(self, unified_validator: UnifiedRiskValidator):
        self.validator = unified_validator
    
    async def validate_trade(
        self,
        proposal: Dict[str, Any],
        user_id: str,
        db_session: AsyncSession,
        exchange: str = "mexc",
        symbol: str = "XAUT/USDT"
    ) -> Any:
        """Old API signature, delegates to new validator."""
        context = RiskContext(user_id=user_id, db_session=db_session)
        decision = await self.validator.validate(proposal, context)
        
        # Return ValidationResult-compatible object
        from app.risk.validator import ValidationResult
        return ValidationResult(
            approved=decision.approved,
            violations=decision.violations,
            warnings=decision.warnings,
        )
```

---

#### Step 3: Update Callers Incrementally

**In execution_service.py:**
```python
# OLD:
from app.risk.risk_engine import RiskEngine
self.risk_engine = RiskEngine(db_session=db_session)
risk_decision = await self.risk_engine.check_trade_approval(...)

# NEW:
from app.risk.unified_validator import UnifiedRiskValidator, RiskContext
self.risk_validator = UnifiedRiskValidator()
context = RiskContext(user_id=user_id, db_session=db_session)
risk_decision = await self.risk_validator.validate(proposal, context)
```

---

### Validation Checklist

- [ ] UnifiedRiskValidator passes all golden tests
- [ ] Legacy adapters return same results as originals
- [ ] All callers updated to use unified validator
- [ ] Deprecated files marked for removal
- [ ] Documentation updated

---

## Task C3: Break Circular Dependencies

### Why This Matters
- **Current State:** Circular imports cause startup failures
- **Problem:** Can't test components in isolation
- **Goal:** Clean dependency graph with no cycles

### Implementation Steps

#### Step 1: Define Interfaces

**Create file:** `app/execution/interfaces.py`

```python
"""Interface definitions for dependency injection."""
from typing import Protocol, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession


class IRiskValidator(Protocol):
    """Interface for risk validation."""
    
    async def validate(
        self,
        proposal: Dict[str, Any],
        context: Any
    ) -> Any:
        """Validate trade proposal against risk rules."""
        ...


class IExchangeConnector(Protocol):
    """Interface for exchange operations."""
    
    async def place_order(self, order_request: Any) -> Any:
        """Place order on exchange."""
        ...
    
    async def get_positions(self) -> List[Dict[str, Any]]:
        """Get current positions."""
        ...
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel order by ID."""
        ...


class INotificationService(Protocol):
    """Interface for notifications."""
    
    async def send_alert(self, message: str, severity: str = "INFO") -> bool:
        """Send notification alert."""
        ...
    
    async def send_trade_notification(self, trade_data: Dict[str, Any]) -> bool:
        """Send trade execution notification."""
        ...
```

---

#### Step 2: Refactor ExecutionService to Use Interfaces

**Update execution_service.py:**
```python
# OLD:
from app.risk.risk_engine import RiskEngine
from app.infra.exchange_manager import UnifiedExchangeManager

class ExecutionService:
    def __init__(self, exchange_name: str, use_testnet: bool):
        self.risk_engine = RiskEngine()
        self.exchange = UnifiedExchangeManager(exchange_name, use_testnet)

# NEW:
from app.execution.interfaces import IRiskValidator, IExchangeConnector

class ExecutionService:
    def __init__(
        self,
        risk_validator: IRiskValidator,
        exchange_connector: IExchangeConnector,
        db_session_factory: callable
    ):
        self.risk_validator = risk_validator
        self.exchange_connector = exchange_connector
        self.db_session_factory = db_session_factory
```

---

#### Step 3: Create Dependency Container

**Create file:** `app/dependency_container.py`

```python
"""Simple dependency injection container."""
from typing import Dict, Type, Any


class DependencyContainer:
    """Registers and resolves dependencies."""
    
    def __init__(self):
        self._instances: Dict[str, Any] = {}
    
    def register(self, interface_name: str, instance: Any):
        """Register an instance for an interface."""
        self._instances[interface_name] = instance
    
    def resolve(self, interface_name: str) -> Any:
        """Resolve an instance by interface name."""
        if interface_name not in self._instances:
            raise KeyError(f"No instance registered for {interface_name}")
        return self._instances[interface_name]


# Global container instance
container = DependencyContainer()
```

---

#### Step 4: Wire Dependencies in main.py

**Update app/main.py lifespan function:**
```python
from app.dependency_container import container
from app.risk.unified_validator import UnifiedRiskValidator
from app.infra.exchange_manager import UnifiedExchangeManager
from app.execution.execution_service import ExecutionService

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up...")
    
    # Register dependencies
    container.register("IRiskValidator", UnifiedRiskValidator())
    container.register("IExchangeConnector", UnifiedExchangeManager(
        exchange_name=settings.ACTIVE_EXCHANGE,
        use_testnet=settings.BINANCE_TESTNET
    ))
    
    # Create services with injected dependencies
    execution_service = ExecutionService(
        risk_validator=container.resolve("IRiskValidator"),
        exchange_connector=container.resolve("IExchangeConnector"),
        db_session_factory=get_session
    )
    
    # Register execution service
    container.register("ExecutionService", execution_service)
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
```

---

### Validation Checklist

- [ ] `lint-imports --show-cycles app` shows zero cycles
- [ ] Application starts without import errors
- [ ] All tests passing
- [ ] Startup time improved

---

## Common Pitfalls & Solutions

### Pitfall 1: Forgetting to Update All Imports
**Symptom:** Import errors after renaming files  
**Solution:** Use IDE refactoring tools or grep to find all references:
```bash
grep -r "from app.execution.trading_service import" app/
grep -r "import trading_service" app/
```

### Pitfall 2: Breaking Backward Compatibility
**Symptom:** API endpoints fail after refactoring  
**Solution:** Keep old methods as wrappers during transition:
```python
async def old_method(self, ...):
    """Deprecated: Use new_method instead."""
    import warnings
    warnings.warn("old_method is deprecated, use new_method", DeprecationWarning)
    return await self.new_method(...)
```

### Pitfall 3: Insufficient Testing
**Symptom:** Bugs discovered in production  
**Solution:** Run full test suite after EACH extraction step, not just at the end

---

## Need Help?

- **Technical Questions:** Review [CODE_REFACTORING_AUDIT_REPORT.md](./CODE_REFACTORING_AUDIT_REPORT.md)
- **Implementation Issues:** Check [REFACTORING_IMPLEMENTATION_CHECKLIST.md](./REFACTORING_IMPLEMENTATION_CHECKLIST.md)
- **Escalation:** Contact tech lead if blocked >2 hours

---

**Good luck with your refactoring! 🚀**
