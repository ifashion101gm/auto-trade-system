# Auto Trade System - Testing Framework

## Overview

This directory contains the comprehensive testing framework for the Auto Trade System. The framework follows the **Testing Pyramid** approach, starting with fast, isolated unit tests and expanding to integration and end-to-end tests.

## Test Structure

```
tests/
├── conftest.py                    # Shared fixtures and utilities
├── unit/                          # Layer 1: Unit Tests
│   ├── __init__.py
│   ├── test_indicators.py         # Technical indicator calculations (ATR, RSI, MA)
│   ├── test_risk_calculations.py  # Risk management calculations (SL/TP, position sizing)
│   ├── test_breakout_strategy.py  # Breakout strategy signal generation
│   ├── test_mean_reversion.py     # Mean reversion strategy signals
│   ├── test_trend_strategy.py     # Trend following strategy signals
│   └── test_risk_engine.py        # Risk engine validation rules
├── integration/                   # Layer 2: Integration Tests (future)
└── e2e/                           # Layer 3: End-to-End Tests (future)
```

## Running Tests

### Run All Unit Tests
```bash
pytest tests/unit/ -v
```

### Run Specific Test File
```bash
pytest tests/unit/test_indicators.py -v
```

### Run Tests with Coverage
```bash
pytest tests/unit/ --cov=app --cov-report=html
# Open htmlcov/index.html in browser to view coverage report
```

### Run Only Fast Tests
```bash
pytest tests/unit/ -m unit --tb=short
```

### Run Single Test Case
```bash
pytest tests/unit/test_indicators.py::TestATRCalculation::test_atr_basic_calculation -v
```

## Writing New Tests

### Test Design Principles

1. **Deterministic**: Use static fixtures with known inputs/outputs
2. **Fast**: No network calls, database access, or external dependencies
3. **Isolated**: Test individual functions in complete isolation
4. **Independent**: No test ordering dependencies

### Test Naming Convention

```python
def test_<function_name>_<scenario>():
    """Test <what is being tested>."""
    # Arrange: Set up test data
    # Act: Call function under test
    # Assert: Verify expected behavior
```

Example:
```python
def test_atr_high_volatility():
    """Test ATR increases with volatility."""
    volatile_ohlcv = create_volatile_ohlcv(gap=50)
    calm_ohlcv = create_calm_ohlcv(gap=5)
    
    atr_volatile = calculate_atr(volatile_ohlcv, period=14)
    atr_calm = calculate_atr(calm_ohlcv, period=14)
    
    assert atr_volatile > atr_calm
```

### Using Fixtures

Fixtures are defined in `tests/conftest.py` and automatically available to all tests:

```python
def test_with_market_data(sample_market_data):
    """Test using shared market data fixture."""
    assert sample_market_data['current_price'] == 50000.0
    assert sample_market_data['rsi'] == 58.3
```

Available fixtures:
- `sample_ohlcv_data`: 50 candles of realistic OHLCV data
- `sample_market_data`: Complete market snapshot with all indicators
- `volatile_ohlcv_data`: High volatility price data
- `calm_ohlcv_data`: Low volatility price data
- `bullish_breakout_ohlcv`: Bullish breakout pattern
- `bearish_breakout_ohlcv`: Bearish breakdown pattern

### Helper Functions

Use helper functions from `conftest.py`:

```python
from tests.conftest import assert_approx_equal

def test_float_comparison():
    """Test float values with tolerance."""
    result = 40.001
    expected = 40.0
    assert_approx_equal(result, expected, tolerance=0.01)  # Passes
```

## Test Categories

### Unit Tests (Layer 1)
- **Location**: `tests/unit/`
- **Purpose**: Test individual functions and classes in isolation
- **Speed**: < 5 seconds total
- **Dependencies**: None (pure functions only)
- **Examples**:
  - Indicator calculations (ATR, RSI, MA)
  - Risk calculations (position sizing, SL/TP)
  - Strategy signal generation logic
  - Risk engine validation rules

### Integration Tests (Layer 2) - Future
- **Location**: `tests/integration/`
- **Purpose**: Test component interactions with mocked external services
- **Speed**: < 30 seconds total
- **Dependencies**: Mocked exchanges, databases
- **Planned Tests**:
  - Strategy + Risk Engine integration
  - Exchange client mocking
  - Database persistence

### End-to-End Tests (Layer 3) - Future
- **Location**: `tests/e2e/`
- **Purpose**: Test complete trading cycles with real/simulated exchanges
- **Speed**: Minutes
- **Dependencies**: Testnet accounts, full system setup
- **Planned Tests**:
  - Complete trade cycle (signal → execution → closure)
  - Multi-exchange failover
  - Crash recovery scenarios

## Code Coverage Goals

- **Unit Tests**: ≥ 80% line coverage for core modules
- **Critical Paths**: 100% coverage for risk management and order execution
- **Overall Target**: ≥ 70% coverage across entire codebase

Check coverage:
```bash
pytest tests/unit/ --cov=app.strategy.indicators --cov=app.risk.calculations --cov-report=term-missing
```

## Best Practices

### DO:
✅ Use descriptive test names that explain the scenario  
✅ Test edge cases (zero values, extreme values, empty inputs)  
✅ Test error conditions (invalid inputs, exceptions)  
✅ Keep tests independent and order-independent  
✅ Use fixtures for common test data  
✅ Mock external dependencies  

### DON'T:
❌ Use network calls in unit tests  
❌ Access real databases in unit tests  
❌ Use random/unpredictable test data  
❌ Make tests depend on execution order  
❌ Test multiple concerns in a single test  
❌ Hardcode API keys or credentials  

## Troubleshooting

### Tests Running Slowly
```bash
# Check which tests are slowest
pytest tests/unit/ --durations=10
```

### Import Errors
```bash
# Ensure you're in project root
cd /home/admin/.openclaw/workspace/auto-trade-system

# Activate virtual environment
source .venv/bin/activate

# Install test dependencies
pip install pytest pytest-cov
```

### Async Test Issues
For async functions, use `asyncio.run()`:
```python
import asyncio

def test_async_function():
    result = asyncio.run(some_async_function())
    assert result == expected
```

## Continuous Integration

Tests will be integrated into CI/CD pipeline:
- Run on every pull request
- Block merge if tests fail
- Generate coverage reports
- Track coverage trends over time

## Future Enhancements

Planned improvements:
1. Property-based testing with Hypothesis
2. Performance benchmarking tests
3. Mutation testing to verify test quality
4. Visual regression tests for dashboard
5. Load testing for WebSocket connections

## Contributing

When adding new features:
1. Write tests first (TDD approach preferred)
2. Ensure all existing tests pass
3. Maintain or improve code coverage
4. Add test documentation for complex scenarios
5. Update this README if adding new test categories

## Support

For questions about testing:
- Review existing tests in `tests/unit/` for examples
- Check pytest documentation: https://docs.pytest.org/
- Consult the plan document: `.lingma/plans/Layer_1_Unit_Testing_Framework_*.md`
