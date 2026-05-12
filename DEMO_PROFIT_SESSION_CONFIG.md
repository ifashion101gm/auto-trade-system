# Demo Trading Session - $100 Profit Target Configuration

**Date**: 2026-05-13  
**Status**: ✅ **CONFIGURED AND READY TO EXECUTE**

---

## 🎯 Objective

Execute an automated trading session in **Demo/Testnet mode** with the specific goal of achieving **$100 USD profit**. The system will continuously monitor trades, track cumulative profit, and automatically terminate when the target is reached.

---

## 🔒 Safety Verification

### Demo Mode Configuration (VERIFIED)

The following environment variables ensure **NO LIVE FINANCIAL RISK**:

```bash
# Binance Testnet Mode - ENABLED ✅
BINANCE_TESTNET=true
BINANCE_DEMO_MODE=futures_demo

# Execution Mode
EXECUTION_MODE=fully-auto
AUTO_EXECUTE_THRESHOLD_USD=100.0

# Active Exchange
ACTIVE_EXCHANGE=binance
```

**Verification Status**: 
- ✅ `BINANCE_TESTNET=true` - System operates on Binance Futures Demo endpoint
- ✅ `BINANCE_DEMO_MODE=futures_demo` - Uses demo-fapi.binance.com
- ✅ No live API keys exposed - All trading uses virtual funds

---

## 📋 Trading Parameters

### 1. Active Strategy

The system uses **AI-powered strategy selection** via OpenRouter LLM integration:

- **Strategy Engine**: Multi-strategy framework with parallel regime detection
- **Available Strategies**:
  - Momentum Strategy (trend-following)
  - Mean Reversion Strategy (counter-trend)
  - Breakout Strategy (volatility-based)
  - London Breakout (session-aware for Gold)
  
- **Strategy Selection**: AI analyzes market conditions and selects optimal strategy
- **Confidence Threshold**: 65% minimum confidence required for trade execution

### 2. Risk Management Settings

#### Stop Loss (SL) Configuration
- **Calculation Method**: Dynamic based on ATR (Average True Range)
- **Default SL Distance**: 2% from entry price
- **ATR Multiplier**: 1.5x ATR for adaptive stops
- **Example**: 
  - Entry Price: $2,800 (PAXG/USDT)
  - Stop Loss: $2,744 (2% below entry for LONG positions)

#### Take Profit (TP) Configuration
- **Calculation Method**: Risk-reward ratio based
- **Default TP Distance**: 4% from entry price
- **Risk-Reward Ratio**: 1:2 (risk $1 to make $2)
- **Example**:
  - Entry Price: $2,800
  - Take Profit: $2,912 (4% above entry for LONG positions)

#### Position Sizing
- **Risk Per Trade**: 1% of account balance
- **Account Balance**: ~$1,000 (demo account starting balance)
- **Risk Amount**: $10 per trade
- **Leverage**: Up to 5x (conservative for demo)
- **Position Size Calculation**:
  ```
  Quantity = (Risk Amount × Leverage) / |Entry Price - Stop Loss|
  Example: ($10 × 3) / |$2,800 - $2,744| = 0.536 PAXG
  ```

### 3. Symbol Configuration

- **Exchange**: Binance Futures Demo
- **Symbol**: PAXG/USDT (Paxos Gold)
- **Asset Type**: Gold-backed cryptocurrency token
- **Trading Hours**: 24/7 (crypto markets)

---

## ⚙️ Execution Configuration

### Trading Service Setup

```python
service = LiveTradingService(
    exchange_name="binance",
    use_testnet=True,          # ✅ Demo mode enforced
    use_openrouter=True        # AI-powered decisions
)
```

### Cycle Parameters

- **Maximum Cycles**: 50 (safety limit)
- **Cycle Interval**: 5 seconds between trades
- **Auto-Execution**: Enabled for positions ≤ $100 USD
- **Quality Filter**: Trades rejected if quality score < threshold

---

## 🚀 Execution Instructions

### Step 1: Verify Configuration

Before executing, verify demo mode is active:

```bash
cd /home/admin/.openclaw/workspace/auto-trade-system
python3 test_config.py
```

Expected output:
```
✅ Configuration loaded successfully!
Binance Testnet: True
Execution Mode: fully-auto
Active Exchange: binance
```

### Step 2: Execute Trading Session

Run the profit-target session script:

```bash
python3 scripts/run_demo_profit_session.py
```

The script will:
1. ✅ Validate demo mode configuration
2. 📊 Display initial balance and parameters
3. 🔄 Execute trading cycles automatically
4. 📈 Track cumulative profit in real-time
5. 🎉 Terminate when $100 profit is reached

### Step 3: Monitor Progress

During execution, you'll see:

```
================================================================================
  CYCLE #1
================================================================================
⏰ Timestamp: 2026-05-13 14:30:00

📊 Stage Results:
   ✅ Market Data Fetch: success
   ✅ AI Analysis: success
   ✅ Trade Proposal: success
   ✅ Order Execution: executed
   ✅ Database Persistence: completed
   ✅ Telegram Notification: sent

⚡ Order Execution:
   • Order ID: 12345678
   • Filled Price: $2,800.50
   • Quantity: 0.5360
   • Position Value: $1,501.07

📊 Profit Tracking:
   • Realized Profit: $+0.00
   • Unrealized P&L: $+12.50
   • Total Current Profit: $+12.50
   • Target: $100.00
   • Progress: 12.5%
```

### Step 4: Session Completion

When target is reached:

```
🎉 PROFIT TARGET REACHED!
   Achieved $102.35 profit (target: $100.00)

================================================================================
  DEMO TRADING SESSION REPORT
================================================================================

📅 Session Summary:
   • Start Time: 2026-05-13 14:30:00 UTC
   • End Time: 2026-05-13 15:45:30 UTC
   • Duration: 1:15:30

📊 Performance Metrics:
   • Total Cycles: 23
   • Successful Trades: 18
   • Rejected (Quality Filter): 4
   • Failed: 1
   • Success Rate: 78.3%

💰 Financial Results:
   • Initial Balance: $1,000.00
   • Final Balance: $1,102.35
   • Total Profit: $+102.35
   • Profit Target: $100.00

🎉 TARGET ACHIEVED!
   Successfully reached $100.00 profit target

🔒 Safety Verification:
   • Demo Mode: ✅ ACTIVE
   • No Live Financial Risk: ✅ CONFIRMED
```

---

## 📊 Monitoring & Validation

### Real-Time Monitoring

The system provides multiple monitoring layers:

1. **Console Output**: Real-time cycle results and profit tracking
2. **Database Persistence**: All trades logged to PostgreSQL
3. **Telegram Notifications**: Instant alerts for trade events (if configured)
4. **Dashboard API**: REST endpoints for programmatic monitoring

### Database Queries

Check open positions:
```sql
SELECT id, symbol, side, entry_price, qty, profit, status
FROM paper_trades
WHERE status = 'open'
ORDER BY ts_open DESC;
```

Check session profit:
```sql
SELECT 
    SUM(profit) as total_profit,
    COUNT(*) as trade_count,
    AVG(profit) as avg_profit_per_trade
FROM paper_trades
WHERE status = 'closed'
  AND ts_close >= '2026-05-13 14:30:00';  -- Session start time
```

### Dashboard API Endpoints

Get current positions:
```bash
curl -X GET "http://localhost:8000/api/trading/paper-trades/open" \
  -H "X-Trading-Secret: change_this_to_a_secure_random_string_12345"
```

Get trade history:
```bash
curl -X GET "http://localhost:8000/api/trading/paper-trades/history?limit=20" \
  -H "X-Trading-Secret: change_this_to_a_secure_random_string_12345"
```

---

## 🛡️ Risk Controls

### Built-in Safety Mechanisms

1. **Circuit Breaker**: Pauses trading after 3 consecutive failures
2. **Daily Loss Limit**: -3% maximum daily loss (configurable)
3. **Max Drawdown**: 15% maximum drawdown from peak balance
4. **Position Size Cap**: 1.5% of balance per position
5. **Leverage Limit**: 5x maximum (conservative for demo)
6. **Quality Filter**: Rejects low-confidence trade proposals
7. **Cooldown Period**: 300-second cooldown after 3 consecutive losses

### Kill Switches

- **Manual Interrupt**: Press `Ctrl+C` to stop session immediately
- **Auto-Pause**: System pauses on critical errors or risk violations
- **Max Cycles**: Hard limit of 50 cycles prevents runaway execution

---

## 🔧 Troubleshooting

### Issue: BINANCE_TESTNET is False

**Solution**: Update `.env` file:
```bash
BINANCE_TESTNET=true
```
Then restart the session.

### Issue: API Connection Errors

**Solution**: Verify API keys are configured:
```bash
cat .env | grep BINANCE_API_KEY
```

For demo mode, keys can be from:
- Regular Binance account with Demo Trading enabled
- Binance Futures Testnet (testnet.binancefuture.com)

### Issue: No Trades Executed (All Rejected)

**Cause**: Quality filter rejecting low-confidence proposals

**Solutions**:
1. Lower `min_confidence` parameter (currently 0.65)
2. Wait for better market conditions
3. Check AI analysis logs for rejection reasons

### Issue: Profit Not Updating

**Solution**: Check database for closed trades:
```bash
python3 -c "
import asyncio
from app.storage.db import get_session
from sqlalchemy import select
from app.storage.models import PaperTrades

async def check():
    async for db in get_session():
        result = await db.execute(
            select(PaperTrades).where(PaperTrades.status == 'closed')
        )
        trades = result.scalars().all()
        print(f'Closed trades: {len(trades)}')
        for t in trades:
            print(f'  Trade #{t.id}: Profit=${t.profit}')

asyncio.run(check())
"
```

---

## 📝 Important Notes

### Demo vs Live Trading

| Feature | Demo Mode | Live Mode |
|---------|-----------|-----------|
| Funds | Virtual (fake money) | Real money |
| API Endpoint | demo-fapi.binance.com | fapi.binance.com |
| Risk | None | Full financial risk |
| Slippage | Simulated | Real market slippage |
| Fill Rates | Idealized | Subject to liquidity |

### Expected Behavior

- **Trade Frequency**: 1-3 trades per minute (depends on market conditions)
- **Rejection Rate**: 20-40% of proposals rejected by quality filter (normal)
- **Profit Volatility**: Expect both winning and losing trades
- **Session Duration**: 30 minutes to 2 hours to reach $100 target

### Best Practices

1. **Monitor Regularly**: Check console output every few cycles
2. **Review Rejections**: Understand why trades are rejected
3. **Adjust Parameters**: Tune leverage/risk based on performance
4. **Document Results**: Save session reports for analysis
5. **Never Use Live Keys**: Keep demo and live credentials separate

---

## 🎓 Learning Outcomes

This demo session demonstrates:

1. ✅ **AI-Powered Trading**: LLM-driven strategy selection and execution
2. ✅ **Risk Management**: Automated SL/TP placement and position sizing
3. ✅ **Quality Control**: Multi-layer validation before trade execution
4. ✅ **Profit Tracking**: Real-time P&L monitoring with target achievement
5. ✅ **Safety First**: Complete isolation from live financial risk

---

## 📞 Support

If you encounter issues:

1. Check logs: `tail -f logs/trading.log`
2. Verify config: `python3 test_config.py`
3. Review documentation: See `COMPLETE_TRADING_CYCLE_REPORT.md`
4. Check database: Use queries in Monitoring section above

---

**Ready to Execute**: Run `python3 scripts/run_demo_profit_session.py` to start the session! 🚀
