# Layer 4: Paper Trading Architecture

## Overview

Paper Trading validates real-world API interactions using demo environments (MEXC Demo Futures, Binance Testnet) without risking capital. This layer bridges the gap between simulation testing and live trading by exposing the system to actual exchange infrastructure, latency, rate limits, and order handling quirks.

## Configuration Requirements

### Environment Variables

Create a `.env.paper` file or set these environment variables:

```bash
# MEXC Demo Futures
MEXC_DEMO_API_KEY=your_demo_api_key_here
MEXC_DEMO_API_SECRET=your_demo_secret_here
MEXC_USE_DEMO=true

# Binance Testnet
BINANCE_TESTNET_API_KEY=your_testnet_api_key_here
BINANCE_TESTNET_API_SECRET=your_testnet_secret_here
BINANCE_USE_TESTNET=true

# Bybit Demo (if available)
BYBIT_DEMO_API_KEY=your_demo_api_key_here
BYBIT_DEMO_API_SECRET=your_demo_secret_here
BYBIT_USE_DEMO=true

# Paper Trading Specific Settings
PAPER_TRADING_MODE=true
PAPER_MAX_POSITION_VALUE=100  # $100 max per trade
PAPER_DAILY_LOSS_LIMIT=-5.0   # -5% hard stop
PAPER_POSITION_SIZE_PCT=1.0   # 1% of account per trade
```

### Test Fixtures

```python
import pytest
from app.exchange.mexc_client import MEXCClient
from app.exchange.binance_client import BinanceClient

@pytest.fixture
def mexc_demo_client():
    """Real MEXC demo client (not mocked)."""
    return MEXCClient(
        api_key=os.getenv('MEXC_DEMO_API_KEY'),
        api_secret=os.getenv('MEXC_DEMO_API_SECRET'),
        demo_mode=True
    )

@pytest.fixture
def binance_testnet_client():
    """Real Binance testnet client (not mocked)."""
    return BinanceClient(
        api_key=os.getenv('BINANCE_TESTNET_API_KEY'),
        api_secret=os.getenv('BINANCE_TESTNET_API_SECRET'),
        testnet=True
    )
```

## Key Metrics to Validate

### 1. API Latency Benchmarks

Measure round-trip time for critical operations:

```python
import time

async def test_order_submission_latency(mexc_demo_client):
    start = time.time()
    result = await mexc_demo_client.create_market_order(
        symbol='BTC/USDT',
        side='buy',
        amount=0.001
    )
    latency_ms = (time.time() - start) * 1000
    
    # Acceptable thresholds
    assert latency_ms < 2000  # <2s for market orders
    print(f"Order submission latency: {latency_ms:.2f}ms")
```

**Target Latencies:**
- Market orders: <2 seconds
- Limit orders: <1.5 seconds
- Position queries: <1 second
- Balance checks: <500ms

### 2. Rate Limit Handling

Verify exponential backoff on 429 responses:

```python
async def test_rate_limit_compliance(exchange_client):
    """Test that system respects exchange rate limits."""
    # Send rapid requests
    for i in range(20):
        try:
            await exchange_client.fetch_ticker('BTC/USDT')
        except RateLimitExceeded:
            # Should implement exponential backoff
            await asyncio.sleep(backoff_time(i))
```

**Expected Behavior:**
- Detect 429 status codes
- Implement exponential backoff (1s, 2s, 4s, 8s, 16s)
- Log rate limit events
- Resume after cooldown period

### 3. Order Rejection Logic

Test various rejection scenarios:

```python
async def test_insufficient_balance_rejection(exchange_client):
    """Verify proper handling of insufficient balance errors."""
    with pytest.raises(OrderRejectedError) as exc_info:
        await exchange_client.create_market_order(
            symbol='BTC/USDT',
            side='buy',
            amount=1000.0  # Exceeds balance
        )
    
    assert "Insufficient balance" in str(exc_info.value)

async def test_invalid_precision_rejection(exchange_client):
    """Verify precision validation before order submission."""
    with pytest.raises(PrecisionError):
        await exchange_client.create_limit_order(
            symbol='BTC/USDT',
            side='buy',
            amount=0.00123456789,  # Too many decimals
            price=50000.123456789
        )
```

**Rejection Scenarios to Test:**
- Insufficient balance
- Invalid price precision
- Invalid quantity precision
- Minimum order size violations
- Maximum position size exceeded
- Leverage limits exceeded

### 4. Slippage Analysis

Compare expected vs actual fill prices:

```python
async def test_slippage_measurement(exchange_client):
    """Measure slippage on market orders."""
    ticker = await exchange_client.fetch_ticker('BTC/USDT')
    expected_price = ticker['ask']  # For buy orders
    
    order = await exchange_client.create_market_order(
        symbol='BTC/USDT',
        side='buy',
        amount=0.01
    )
    
    actual_price = order['price']
    slippage_pct = abs(actual_price - expected_price) / expected_price * 100
    
    print(f"Slippage: {slippage_pct:.4f}%")
    
    # Slippage should be reasonable (<0.5% for liquid pairs)
    assert slippage_pct < 0.5
```

**Acceptable Slippage:**
- BTC/USDT: <0.1%
- ETH/USDT: <0.15%
- Altcoins: <0.5%

### 5. Symbol Precision and Contract Size

Validate exchange-specific constraints:

```python
async def test_symbol_precision_validation(exchange_client):
    """Verify correct precision for different symbols."""
    precision_rules = {
        'BTC/USDT': {'price': 2, 'quantity': 3},
        'ETH/USDT': {'price': 2, 'quantity': 3},
        'SOL/USDT': {'price': 3, 'quantity': 2}
    }
    
    for symbol, rules in precision_rules.items():
        info = await exchange_client.fetch_symbol_info(symbol)
        
        assert info['price_precision'] == rules['price']
        assert info['quantity_precision'] == rules['quantity']
        assert info['min_order_size'] > 0
```

## Test Structure

```
tests/paper_trading/
├── __init__.py
├── conftest.py                      # Real exchange client fixtures
├── test_mexc_demo_orders.py         # MEXC demo futures tests
├── test_binance_testnet_orders.py   # Binance testnet tests
├── test_bybit_demo_orders.py        # Bybit demo tests (if available)
├── test_latency_benchmarks.py       # API performance measurements
├── test_precision_validation.py     # Symbol constraint validation
├── test_rate_limit_handling.py      # Rate limit compliance tests
└── test_slippage_analysis.py        # Fill price accuracy tests
```

## Safety Mechanisms

### Balance Caps
- Maximum $100 per trade
- Maximum 5% of account balance per position
- Hard-coded limits cannot be overridden

### Daily Loss Limits
- Automatic trading halt at -5% daily loss
- Requires manual reset to resume
- Alert sent via Telegram

### Position Size Limits
- Maximum 1% of account per trade
- Leverage capped at 3x for paper trading
- No martingale or position scaling

### Manual Confirmation
- All trades require explicit confirmation flag
- Separate API keys from production
- Clear visual indicators in dashboard ("PAPER TRADING MODE")

## Running Paper Trading Tests

```bash
# Run all paper trading tests
pytest tests/paper_trading/ -v --paper-trading

# Run specific exchange tests
pytest tests/paper_trading/test_mexc_demo_orders.py -v

# Run with latency benchmarks
pytest tests/paper_trading/test_latency_benchmarks.py -v --benchmark-only

# Skip paper trading tests (default behavior)
pytest tests/ -v  # Excludes @pytest.mark.paper_trading
```

## CI/CD Integration

Paper trading tests should NOT run in automated CI/CD pipelines due to:
- External API dependencies
- Rate limit consumption
- Demo account state changes

Instead, run manually before:
- Deploying new exchange integrations
- Upgrading order execution logic
- Changing precision/rate limit handling

## Success Criteria

Before proceeding to Shadow Mode (Layer 5):

✅ All order types execute successfully  
✅ Latency within acceptable bounds (<2s for market orders)  
✅ Rate limits respected with proper backoff  
✅ Precision validation prevents rejections  
✅ Slippage <0.5% on liquid pairs  
✅ Error handling graceful (no crashes)  
✅ 50+ successful test trades executed  
✅ Zero unexpected rejections  

## Next Steps

After passing all paper trading tests:
1. Review latency logs for optimization opportunities
2. Analyze slippage patterns across different pairs
3. Document exchange-specific quirks discovered
4. Proceed to Layer 5: Shadow Mode for live data validation
