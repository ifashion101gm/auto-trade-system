# Hybrid Execution Mode - Position-Based Auto-Execution

## Overview

The Auto Trade System now implements an intelligent **Hybrid Execution Mode** that automatically routes trades based on position size. This provides the best of both worlds: automation for small, low-risk trades and manual control for larger positions.

---

## 🎯 How It Works

### Execution Mode: `semi-auto` (Default)

When `EXECUTION_MODE=semi-auto`, the system checks the **position value in USD** before executing:

```
Position Value = Entry Price × Quantity
```

#### Decision Logic:

1. **Position ≤ $100 USD**: 
   - ✅ **Auto-execute** immediately (fully-auto behavior)
   - No manual confirmation required
   - Ideal for testing and small trades

2. **Position > $100 USD**: 
   - ⏸️ **Require confirmation** (semi-auto behavior)
   - Proposal saved to database
   - Manual approval needed via API or Telegram

---

## ⚙️ Configuration

### Environment Variables (.env)

```bash
# Execution Mode
EXECUTION_MODE=semi-auto

# Auto-Execute Threshold (USD)
# Positions at or below this value execute automatically
AUTO_EXECUTE_THRESHOLD_USD=100.0
```

### Customizing the Threshold

You can adjust the threshold based on your risk tolerance:

```bash
# Conservative: Only very small trades auto-execute
AUTO_EXECUTE_THRESHOLD_USD=50.0

# Balanced: Small to medium trades auto-execute (default)
AUTO_EXECUTE_THRESHOLD_USD=100.0

# Aggressive: Larger trades auto-execute
AUTO_EXECUTE_THRESHOLD_USD=500.0
```

**Restart the server** after changing the threshold:
```bash
pkill -f "uvicorn app.main:app"
source .venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 📊 Position Sizing

The system calculates position sizes using the **Deterministic Risk Manager**:

### Formula:
```python
risk_amount = account_balance × risk_per_trade × confidence
quantity = risk_amount / (entry_price - stop_loss_price)
position_value_usd = entry_price × quantity
```

### Example Calculation:

Given:
- Account Balance: $10,000
- Risk Per Trade: 1% (0.01)
- Confidence: 0.8 (80%)
- Entry Price: $50,000 (BTC)
- Stop Loss: $49,000
- Regime: Normal (Leverage: 2x)

```python
risk_amount = 10000 × 0.01 × 0.8 = $80
price_diff = 50000 - 49000 = $1000
quantity = 80 / 1000 = 0.08 BTC
position_value = 50000 × 0.08 = $4,000
```

**Result**: Position value is $4,000 → **Requires confirmation** (> $100)

### Lower Risk Example:

Given:
- Account Balance: $1,000
- Risk Per Trade: 1% (0.01)
- Confidence: 0.6 (60%)
- Entry Price: $3,000 (ETH)
- Stop Loss: $2,950

```python
risk_amount = 1000 × 0.01 × 0.6 = $6
price_diff = 3000 - 2950 = $50
quantity = 6 / 50 = 0.12 ETH
position_value = 3000 × 0.12 = $360
```

**Result**: Position value is $360 → **Requires confirmation** (> $100)

### Small Position Example:

Given:
- Account Balance: $500
- Risk Per Trade: 1% (0.01)
- Confidence: 0.5 (50%)
- Entry Price: $25,000
- Stop Loss: $24,800

```python
risk_amount = 500 × 0.01 × 0.5 = $2.50
price_diff = 25000 - 24800 = $200
quantity = 2.50 / 200 = 0.0125
position_value = 25000 × 0.0125 = $312.50
```

**Result**: Position value is $312.50 → **Requires confirmation** (> $100)

To get auto-execution, you need smaller positions:

```python
# For $100 position with $25,000 entry price:
quantity = 100 / 25000 = 0.004
risk_amount = 0.004 × 200 = $0.80
account_balance = 0.80 / (0.01 × 0.5) = $160
```

**With a $160 account balance**, this trade would auto-execute.

---

## 🔧 Implementation Details

### Files Modified:

1. **`app/config.py`**
   - Added `AUTO_EXECUTE_THRESHOLD_USD` configuration parameter
   - Default value: 100.0

2. **`app/services/live_trading_service.py`**
   - Updated `_execute_trade()` method with hybrid logic
   - Calculates `position_value_usd = entry_price × quantity`
   - Routes based on threshold comparison

3. **`app/ai/optimized_orchestrator.py`**
   - Updated `run_optimized_cycle()` with hybrid execution check
   - Applies same threshold logic for consistency

4. **`.env`**
   - Added `AUTO_EXECUTE_THRESHOLD_USD=100.0`
   - Documented hybrid mode behavior

### Code Flow:

```python
# In live_trading_service.py
position_value_usd = entry_price * quantity

if execution_mode == 'semi-auto':
    if position_value_usd <= AUTO_EXECUTE_THRESHOLD_USD:
        # Auto-execute (small position)
        should_auto_execute = True
        print(f"⚡ Auto-executing (small position: ${position_value_usd:.2f})")
    else:
        # Require confirmation (large position)
        return {'status': 'awaiting_confirmation', ...}
```

---

## 📈 Use Cases

### 1. Testing & Development
```bash
AUTO_EXECUTE_THRESHOLD_USD=1000.0  # Higher threshold for testing
EXECUTION_MODE=semi-auto
```
- Most trades auto-execute
- Faster iteration during development
- Still have safety net for very large positions

### 2. Conservative Trading
```bash
AUTO_EXECUTE_THRESHOLD_USD=50.0  # Lower threshold
EXECUTION_MODE=semi-auto
```
- Only very small trades auto-execute
- Manual review for most positions
- Maximum control and safety

### 3. Balanced Approach (Default)
```bash
AUTO_EXECUTE_THRESHOLD_USD=100.0  # Default
EXECUTION_MODE=semi-auto
```
- Small trades automated
- Large trades require approval
- Good balance of convenience and safety

### 4. Semi-Automated Scaling
```bash
AUTO_EXECUTE_THRESHOLD_USD=250.0  # Medium threshold
EXECUTION_MODE=semi-auto
```
- More trades auto-execute as confidence grows
- Still maintain control over significant positions

---

## 🎮 Execution Modes Comparison

| Mode | Position ≤ $100 | Position > $100 | Use Case |
|------|----------------|-----------------|----------|
| **proposal** | Manual | Manual | Full manual control |
| **semi-auto** (hybrid) | **Auto** | Manual | **Best of both worlds** ⭐ |
| **fully-auto** | Auto | Auto | Complete automation |

---

## 🔍 Monitoring & Logging

### Console Output:

**Small Position (Auto-Execute)**:
```
💰 Position value: $75.50 ≤ $100.00
⚡ Auto-executing (small position)
✅ Order executed: ORDER_ID_12345
✅ Filled at: $50,123.45
```

**Large Position (Awaiting Confirmation)**:
```
💰 Position value: $250.00 > $100.00
⏸️  Awaiting confirmation (large position)
Proposal saved. Position value $250.00 exceeds $100.00 threshold.
Call confirm endpoint to execute.
```

### Database Records:

Trade proposals include `position_value_usd` in metadata:
```json
{
  "regime": "Normal",
  "risk_level": "medium",
  "position_value_usd": 75.50
}
```

Paper trades track execution mode:
```python
execution_mode='auto'  # If ≤ $100
execution_mode='fully-auto'  # If > $100 in fully-auto mode
```

---

## 🛡️ Safety Features

### 1. Testnet First
```bash
BINANCE_TESTNET=true  # Default - no real money at risk
```

### 2. Risk Management
- Position sizing based on account balance
- Max 1% risk per trade (configurable)
- Stop-loss enforcement
- Daily drawdown limits

### 3. Circuit Breaker
- Pauses after consecutive failures
- Loss streak protection
- Manual pause/resume capability

### 4. Confirmation for Large Trades
- Positions > $100 require approval
- Prevents accidental large exposures
- Time to review strategy and market conditions

---

## 📝 API Endpoints

### Generate Trade Proposal
```bash
curl -X POST http://localhost:8000/api/v1/trading/paper-trading/run-cycle \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BTC/USDT", "user_id": "user1"}'
```

**Response includes**:
```json
{
  "status": "executed" or "awaiting_confirmation",
  "position_value_usd": 75.50,
  "auto_executed": true,
  "message": "..."
}
```

### Confirm Large Trade (if awaiting confirmation)
```bash
curl -X POST http://localhost:8000/api/v1/trading/confirm-trade/{proposal_id}
```

---

## 🎯 Best Practices

### 1. Start Conservative
```bash
# Week 1-2: Low threshold
AUTO_EXECUTE_THRESHOLD_USD=50.0

# Monitor results and adjust
```

### 2. Gradually Increase
```bash
# After 50+ successful small trades:
AUTO_EXECUTE_THRESHOLD_USD=100.0  # Default

# After 100+ successful trades:
AUTO_EXECUTE_THRESHOLD_USD=200.0
```

### 3. Adjust Based on Account Size
```python
# Rule of thumb: threshold ≈ 10-20% of account balance
account_balance = 1000
threshold = 100  # 10%

account_balance = 5000
threshold = 500  # 10%
```

### 4. Monitor Performance
```bash
# Check trade history
curl http://localhost:8000/api/v1/trading/paper-trading/history

# Filter by execution mode
# Review auto-executed vs confirmed trades
```

---

## 🔧 Troubleshooting

### Issue: All trades require confirmation
**Solution**: Check position values
```bash
# Verify threshold is set correctly
python -c "from app.config import settings; print(settings.AUTO_EXECUTE_THRESHOLD_USD)"

# Check actual position values in logs
# Look for: "Position value: $XXX.XX"
```

### Issue: Trades not auto-executing despite small size
**Solution**: Verify execution mode
```bash
# Check current mode
python -c "from app.config import settings; print(settings.EXECUTION_MODE)"

# Should be: semi-auto or fully-auto
# If proposal mode, no auto-execution occurs
```

### Issue: Want to change threshold
**Solution**: Update .env and restart
```bash
# Edit .env
nano .env
# Change: AUTO_EXECUTE_THRESHOLD_USD=150.0

# Restart server
pkill -f "uvicorn app.main:app"
source .venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 📊 Performance Metrics

Track these metrics to optimize your threshold:

1. **Auto-Execution Rate**
   - % of trades that auto-execute
   - Target: 60-80% for balanced approach

2. **Confirmation Rate**
   - % of trades requiring approval
   - Indicates threshold appropriateness

3. **Average Position Size**
   - Mean position value in USD
   - Helps calibrate threshold

4. **Win Rate by Size**
   - Compare performance: auto vs confirmed
   - Adjust threshold based on results

---

## 🚀 Summary

The **Hybrid Execution Mode** provides:

✅ **Automation** for small, low-risk trades  
✅ **Control** for larger, significant positions  
✅ **Flexibility** with configurable threshold  
✅ **Safety** with testnet and risk management  
✅ **Transparency** with clear logging and notifications  

**Default Configuration**:
- Mode: `semi-auto`
- Threshold: `$100 USD`
- Result: Smart routing based on position size

This approach maximizes efficiency while maintaining appropriate safeguards for your trading capital.

---

*Last Updated: May 11, 2026*  
*Version: 1.0*
