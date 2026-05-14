# 📋 Code Refactoring Implementation Checklist

**Based on:** [CODE_REFACTORING_AUDIT_REPORT.md](./CODE_REFACTORING_AUDIT_REPORT.md)  
**Start Date:** May 15, 2026  
**Target Completion:** July 24, 2026 (10 weeks)  

---

## 🔴 CRITICAL Priority (Weeks 1-2)

### C1: Split LiveTradingService God Class
**Owner:** [Assign developer]  
**Estimated Effort:** 40 hours  
**Risk Level:** HIGH (mitigated by tests)

#### Pre-Refactoring Preparation
- [ ] Create backup branch: `git checkout -b backup/pre-refactor-$(date +%Y%m%d)`
- [ ] Run full test suite: `pytest tests/ -v --tb=short`
- [ ] Document current API endpoints and request/response formats
- [ ] Identify all callers of `LiveTradingService` methods
- [ ] Create integration tests for `execute_trading_cycle()` (if not exists)

#### Implementation Steps
- [ ] **Day 1:** Create new module structure
  - [ ] `mkdir -p app/execution/orchestrators`
  - [ ] `mkdir -p app/execution/coordinators`
  - [ ] `mkdir -p app/execution/services`
  - [ ] Add `__init__.py` files to each directory

- [ ] **Day 2:** Extract state machine logic
  - [ ] Create `app/execution/orchestrators/state_machine_manager.py`
  - [ ] Move state transition logic from `trading_service.py` lines 200-350
  - [ ] Write unit tests for `StateMachineManager`
  - [ ] Update `trading_service.py` to use new manager
  - [ ] Run tests: `pytest tests/unit/test_state_machine_manager.py -v`

- [ ] **Day 3:** Extract signal coordination
  - [ ] Create `app/execution/coordinators/signal_coordinator.py`
  - [ ] Move signal generation logic from `trading_service.py` lines 450-500
  - [ ] Write unit tests for `SignalCoordinator`
  - [ ] Update imports in `trading_service.py`
  - [ ] Run tests: `pytest tests/unit/test_signal_coordinator.py -v`

- [ ] **Day 4:** Extract trade execution
  - [ ] Create `app/execution/services/trade_executor.py`
  - [ ] Move order placement logic from `trading_service.py` lines 600-700
  - [ ] Delegate to existing `ExecutionService` (avoid duplication)
  - [ ] Write unit tests for `TradeExecutor`
  - [ ] Run tests: `pytest tests/unit/test_trade_executor.py -v`

- [ ] **Day 5:** Extract position monitoring
  - [ ] Create `app/execution/services/position_monitor_service.py`
  - [ ] Move monitoring logic from `trading_service.py` lines 800-900
  - [ ] Integrate with existing `PositionMonitor` class
  - [ ] Write unit tests
  - [ ] Run tests

- [ ] **Day 6:** Extract reconciliation coordination
  - [ ] Create `app/execution/coordinators/reconciliation_coordinator.py`
  - [ ] Move reconciliation logic from `trading_service.py` lines 1000-1100
  - [ ] Integrate with existing `ReconciliationAgent`
  - [ ] Write unit tests
  - [ ] Run tests

- [ ] **Day 7:** Create thin orchestrator
  - [ ] Create `app/execution/orchestrators/trading_orchestrator.py`
  - [ ] Wire all extracted components together
  - [ ] Keep `LiveTradingService` as backward-compatible wrapper
  - [ ] Add deprecation warnings to old methods
  - [ ] Run full test suite: `pytest tests/ -v`

#### Post-Refactoring Validation
- [ ] All unit tests passing (>90% coverage for new modules)
- [ ] All integration tests passing
- [ ] No regression in trading functionality (manual testing)
- [ ] Performance benchmark: Compare latency before/after
- [ ] Code review completed by 2+ team members
- [ ] Documentation updated (README, API docs)

#### Deployment
- [ ] Deploy to staging environment
- [ ] Run smoke tests in staging
- [ ] Monitor error logs for 24 hours
- [ ] Deploy to production during low-traffic window
- [ ] Monitor production metrics for 48 hours
- [ ] If issues: Rollback using feature flag

**Success Criteria:**
- ✅ `trading_service.py` reduced from 1,425 to <300 lines
- ✅ Each new module <200 lines
- ✅ Zero test failures
- ✅ No performance degradation (<5% latency increase acceptable)

---

### C2: Consolidate Risk Validation Logic
**Owner:** [Assign developer]  
**Estimated Effort:** 30 hours  
**Risk Level:** MEDIUM (mitigated by golden test suite)

#### Pre-Refactoring Preparation
- [ ] Inventory all risk checks across 3 files
- [ ] Create comparison spreadsheet showing differences
- [ ] Identify "best" implementation for each check
- [ ] Create golden test suite with 50+ scenarios

#### Implementation Steps
- [ ] **Day 1:** Design unified interface
  - [ ] Create `app/risk/unified_validator.py`
  - [ ] Define `RiskContext`, `RiskDecision` dataclasses
  - [ ] Define `UnifiedRiskValidator` class skeleton
  - [ ] Write interface documentation

- [ ] **Day 2-3:** Implement individual risk checks
  - [ ] `_check_emergency_stop()` - Use best logic from existing
  - [ ] `_check_circuit_breaker()` - Integrate with circuit breaker
  - [ ] `_check_daily_loss_limit()` - Consolidate from 3 implementations
  - [ ] `_check_drawdown_limit()` - Standardize calculation
  - [ ] `_check_position_size()` - Unified formula
  - [ ] `_check_leverage_limit()` - Single source of truth
  - [ ] `_check_concurrent_positions()` - New check if missing
  - [ ] `_check_volatility_chaos()` - From risk_engine.py
  - [ ] `_check_slippage_risk()` - From risk_engine.py
  - [ ] Write unit test for EACH check

- [ ] **Day 4:** Implement orchestration logic
  - [ ] `validate()` method runs checks in priority order
  - [ ] Short-circuit on first failure (fail-fast)
  - [ ] Collect all warnings even if approved
  - [ ] Return structured `RiskDecision`
  - [ ] Add comprehensive logging

- [ ] **Day 5:** Create legacy adapters
  - [ ] `LegacyRiskEngineAdapter` wraps unified validator
  - [ ] `LegacyRiskManagerAdapter` wraps unified validator
  - [ ] `LegacyTradeValidatorAdapter` wraps unified validator
  - [ ] Ensure adapters return same format as originals
  - [ ] Test adapters against golden test suite

- [ ] **Day 6:** Update callers incrementally
  - [ ] Update `execution_service.py` to use unified validator
  - [ ] Update `trading_service.py` to use unified validator
  - [ ] Update agents to use unified validator
  - [ ] Run tests after each update

- [ ] **Day 7:** Deprecation and cleanup
  - [ ] Add deprecation warnings to old validators
  - [ ] Update documentation to point to unified validator
  - [ ] Schedule removal date (2 weeks from now)
  - [ ] Run full test suite

#### Gradual Rollout Plan
- [ ] **Week 1:** 10% of traffic uses unified validator
  - [ ] Monitor error rates
  - [ ] Compare decisions vs legacy validators
  - [ ] Fix any discrepancies

- [ ] **Week 2:** 50% of traffic
  - [ ] Continue monitoring
  - [ ] Gather developer feedback

- [ ] **Week 3:** 100% of traffic
  - [ ] Remove feature flag
  - [ ] Delete deprecated files

#### Post-Refactoring Validation
- [ ] Golden test suite passes 100%
- [ ] No discrepancies between old and new validators
- [ ] Code duplication reduced by >80%
- [ ] All callers updated successfully

**Success Criteria:**
- ✅ Single `UnifiedRiskValidator` class
- ✅ 400+ lines of duplicated code removed
- ✅ All risk checks pass golden test suite
- ✅ Zero regression in risk enforcement

---

### C3: Break Circular Dependencies
**Owner:** [Assign developer]  
**Estimated Effort:** 20 hours  
**Risk Level:** LOW (mechanical refactoring)

#### Pre-Refactoring Preparation
- [ ] Map current dependency graph: `lint-imports --show-cycles app`
- [ ] Identify all circular import chains
- [ ] Document which modules depend on which

#### Implementation Steps
- [ ] **Day 1:** Define interfaces
  - [ ] Create `app/execution/interfaces.py`
  - [ ] Define `IRiskValidator` Protocol
  - [ ] Define `IExchangeConnector` Protocol
  - [ ] Define `INotificationService` Protocol
  - [ ] Define `IDatabaseSession` Protocol
  - [ ] Add type hints to all protocols

- [ ] **Day 2:** Refactor ExecutionService
  - [ ] Change constructor to accept dependencies
  - [ ] Replace concrete imports with interface imports
  - [ ] Update type hints to use Protocols
  - [ ] Write unit tests with mock dependencies

- [ ] **Day 3:** Refactor RiskEngine
  - [ ] Accept `IExchangeConnector` via constructor
  - [ ] Remove direct import of `UnifiedExchangeManager`
  - [ ] Use dependency injection pattern
  - [ ] Write unit tests

- [ ] **Day 4:** Create dependency container
  - [ ] Create `app/dependency_container.py`
  - [ ] Implement simple DI container (or use `dependency-injector`)
  - [ ] Register all services at startup
  - [ ] Resolve dependencies when creating instances

- [ ] **Day 5:** Update main.py initialization
  - [ ] Wire up dependencies in `lifespan()` function
  - [ ] Pass dependencies to service constructors
  - [ ] Remove lazy imports (no more `__getattr__` hacks)
  - [ ] Test application startup

- [ ] **Day 6:** Verify no cycles
  - [ ] Run `lint-imports --enforce-contracts`
  - [ ] Run `python -c "import app.main"` - should start cleanly
  - [ ] Check startup time improved
  - [ ] Run full test suite

#### Post-Refactoring Validation
- [ ] Zero circular dependencies detected
- [ ] Application starts without import errors
- [ ] Startup time reduced by >20%
- [ ] All tests passing

**Success Criteria:**
- ✅ `lint-imports` shows zero cycles
- ✅ No lazy imports needed
- ✅ All dependencies explicit in constructors
- ✅ Faster application startup

---

## 🟡 HIGH Priority (Weeks 3-4)

### H1: Standardize Naming Conventions
**Owner:** [Assign developer]  
**Estimated Effort:** 15 hours  
**Risk Level:** LOW (automated refactoring)

#### Implementation Steps
- [ ] **Day 1:** Rename duplicate files
  - [ ] Rename root-level `execution_agent.py` → `order_execution_service.py`
  - [ ] Update all imports
  - [ ] Run tests

- [ ] **Day 2:** Standardize agent names
  - [ ] `signal_agent.py` → `signal_generation_agent.py`
  - [ ] `execution_agent.py` → `order_placement_agent.py`
  - [ ] `monitoring_agent.py` → `health_monitoring_agent.py`
  - [ ] `recovery_agent.py` → `failure_recovery_agent.py`
  - [ ] `reconciliation_agent.py` → `data_reconciliation_agent.py`
  - [ ] Update all imports

- [ ] **Day 3:** Rename ambiguous variables
  - [ ] `self.exchange_name` → `self.active_exchange`
  - [ ] `self.use_testnet` → `self.is_testnet_mode`
  - [ ] `self.symbol_locks` → `self.per_symbol_execution_locks`
  - [ ] Search and replace throughout codebase
  - [ ] Run tests

- [ ] **Day 4:** Standardize suffixes
  - [ ] All services end with `_service.py`
  - [ ] All managers end with `_manager.py`
  - [ ] All detectors end with `_detector.py`
  - [ ] Rename files as needed
  - [ ] Update imports

- [ ] **Day 5:** Add naming convention guide
  - [ ] Create `docs/NAMING_CONVENTIONS.md`
  - [ ] Document file naming rules
  - [ ] Document variable naming rules
  - [ ] Document class naming rules
  - [ ] Add to CONTRIBUTING.md

#### Validation
- [ ] All files follow naming conventions
- [ ] No duplicate filenames at different levels
- [ ] Variable names are self-documenting
- [ ] Team agrees on conventions

---

### H2: Reduce Cyclomatic Complexity
**Owner:** [Assign developer]  
**Estimated Effort:** 25 hours  
**Risk Level:** MEDIUM (requires careful extraction)

#### Implementation Steps
- [ ] **Day 1-2:** Refactor `execute_trading_cycle()`
  - [ ] Extract `_validate_preflight()` method
  - [ ] Extract `_generate_and_validate_signal()` method
  - [ ] Extract `_execute_based_on_mode()` method
  - [ ] Extract `_handle_post_execution()` method
  - [ ] Measure complexity before/after: `radon cc trading_service.py`
  - [ ] Target: <10 per method

- [ ] **Day 3-4:** Refactor `check_trade_approval()`
  - [ ] Apply strategy pattern (see audit report section 1.4.2)
  - [ ] Create individual check classes
  - [ ] Replace nested conditionals with check list
  - [ ] Measure complexity before/after
  - [ ] Target: <10 per method

- [ ] **Day 5:** Apply guard clauses throughout
  - [ ] Replace nested `if` with early returns
  - [ ] Example:
    ```python
    # Before
    if condition_a:
        if condition_b:
            do_something()
    
    # After
    if not condition_a:
        return
    if not condition_b:
        return
    do_something()
    ```
  - [ ] Apply to top 10 most complex methods

- [ ] **Day 6:** Replace conditionals with lookup tables
  - [ ] Identify switch-case patterns
  - [ ] Replace with dictionary lookups
  - [ ] Example:
    ```python
    # Before
    if mode == 'proposal':
        handler = proposal_handler
    elif mode == 'semi-auto':
        handler = semi_auto_handler
    else:
        handler = fully_auto_handler
    
    # After
    handlers = {
        'proposal': proposal_handler,
        'semi-auto': semi_auto_handler,
        'fully-auto': fully_auto_handler,
    }
    handler = handlers.get(mode, default_handler)
    ```

- [ ] **Day 7:** Add complexity checks to CI
  - [ ] Install `radon`: `pip install radon`
  - [ ] Add to pre-commit hooks
  - [ ] Configure threshold: max complexity = 10
  - [ ] Fail CI if threshold exceeded

#### Validation
- [ ] Average complexity <5 (measured by `radon cc`)
- [ ] Max complexity <10
- [ ] All methods easier to understand (team survey)
- [ ] Branch coverage increased

---

### H3: Implement Repository Pattern
**Owner:** [Assign developer]  
**Estimated Effort:** 20 hours  
**Risk Level:** LOW (additive change)

#### Implementation Steps
- [ ] **Day 1:** Create repository base class
  - [ ] `app/database/repositories/base_repository.py`
  - [ ] Define common methods: `get_by_id()`, `list()`, `create()`, `update()`, `delete()`
  - [ ] Add type hints
  - [ ] Write unit tests with mocked session

- [ ] **Day 2:** Implement TradeRepository
  - [ ] `app/database/repositories/trade_repository.py`
  - [ ] Move queries from `risk_engine.py`, `validator.py`, etc.
  - [ ] Methods: `get_today_trades()`, `calculate_daily_pnl()`, `count_open_positions()`
  - [ ] Write unit tests
  - [ ] Write integration tests with real DB

- [ ] **Day 3:** Implement UserRepository
  - [ ] `app/database/repositories/user_repository.py`
  - [ ] Methods: `get_user()`, `get_user_balance()`, `get_user_positions()`
  - [ ] Write tests

- [ ] **Day 4:** Implement PositionRepository
  - [ ] `app/database/repositories/position_repository.py`
  - [ ] Methods: `get_open_positions()`, `get_position_by_id()`, `update_position()`
  - [ ] Write tests

- [ ] **Day 5-6:** Update callers
  - [ ] Replace direct SQLAlchemy calls with repository methods
  - [ ] Start with `risk_engine.py`
  - [ ] Then `trading_service.py`
  - [ ] Then agents
  - [ ] Run tests after each file

- [ ] **Day 7:** Add caching layer (optional)
  - [ ] Wrap repositories with cache decorator
  - [ ] Use Redis for cache storage
  - [ ] Add cache invalidation logic
  - [ ] Benchmark performance improvement

#### Validation
- [ ] All database queries go through repositories
- [ ] Zero direct SQLAlchemy calls in business logic
- [ ] Unit tests can mock repositories easily
- [ ] Query count reduced (if caching added)

---

## 🟢 MEDIUM Priority (Weeks 5-6)

### M1: Eliminate Order Placement Duplication
**Owner:** [Assign developer]  
**Estimated Effort:** 15 hours  

#### Implementation Steps
- [ ] Audit all order placement implementations
- [ ] Keep `ExecutionService.execute_trade()` as canonical
- [ ] Refactor `ExecutionAgent` to delegate to `ExecutionService`
- [ ] Remove duplicate logic from `trading_service.py`
- [ ] Add comprehensive tests for `ExecutionService`
- [ ] Update documentation

---

### M2: Add Type Annotations
**Owner:** [Assign developer]  
**Estimated Effort:** 20 hours  

#### Implementation Steps
- [ ] Run `mypy --strict` to identify missing annotations
- [ ] Add type hints to all function signatures
- [ ] Use TypedDict for complex dictionaries
- [ ] Add return type annotations
- [ ] Configure mypy in CI
- [ ] Fix all mypy errors

---

### M3: Standardize Error Handling
**Owner:** [Assign developer]  
**Estimated Effort:** 15 hours  

#### Implementation Steps
- [ ] Define custom exception hierarchy
- [ ] Wrap all external API calls
- [ ] Log errors with correlation IDs
- [ ] Return structured error responses
- [ ] Add error codes for programmatic handling

---

## 🔵 NICE TO HAVE (Ongoing)

### N1: Add Comprehensive Docstrings
**Effort:** Ongoing  
**Action:** Add Google-style docstrings to all public methods

### N2: Optimize Database Queries
**Effort:** 10 hours  
**Action:** Eliminate N+1 queries, add indexes, implement caching

### N3: Add Performance Monitoring
**Effort:** 8 hours  
**Action:** Add Prometheus histograms, create Grafana dashboard

---

## Weekly Progress Tracking

### Week 1 Checklist
- [ ] C1: State machine extracted
- [ ] C1: Signal coordinator extracted
- [ ] C2: Unified validator designed
- [ ] C3: Interfaces defined

### Week 2 Checklist
- [ ] C1: All components extracted
- [ ] C1: Tests passing
- [ ] C2: Unified validator implemented
- [ ] C3: Circular dependencies broken

### Week 3 Checklist
- [ ] H1: Naming conventions standardized
- [ ] H2: Complexity reduced for top 5 methods
- [ ] H3: Repositories created

### Week 4 Checklist
- [ ] H2: All methods <10 complexity
- [ ] H3: All callers updated to use repositories
- [ ] M1: Order placement deduplicated

### Week 5 Checklist
- [ ] M2: Type annotations added to 50% of code
- [ ] M3: Error handling standardized
- [ ] N1: Docstrings added to critical modules

### Week 6 Checklist
- [ ] M2: 100% type annotation coverage
- [ ] All medium priority items complete
- [ ] Final validation testing

---

## Success Metrics Dashboard

Track these metrics weekly:

| Metric | Week 0 | Week 2 | Week 4 | Week 6 | Target |
|--------|--------|--------|--------|--------|--------|
| Avg. Complexity | 12 | | | | <5 |
| Max Complexity | 25+ | | | | <10 |
| Code Duplication | 15% | | | | <5% |
| Type Coverage | 40% | | | | 100% |
| Test Coverage | 60% | | | | 85% |
| Lines/File (avg) | 450 | | | | <200 |
| Circular Deps | 3 | | | | 0 |

---

## Blockers & Escalation

### Current Blockers
- [List any blockers here]

### Escalation Path
1. Technical issues → Tech Lead
2. Resource constraints → Engineering Manager
3. Timeline risks → Project Manager

---

**Last Updated:** May 15, 2026  
**Next Review:** May 22, 2026 (Weekly sync)
