# Paper Trading Quick Start Guide

## 🚀 Getting Started in 5 Minutes

### Step 1: Configure Environment
Create or update `.env` file in project root:

```env
# Required: Trading API Security
TRADING_API_SECRET=my_secure_secret_123

# Optional: Telegram Notifications
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789

# Optional: LLM Providers (for AI analysis)
OPENAI_API_KEY=sk-your-key-here
```

### Step 2: Start the Server
```bash
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Step 3: Run Validation
```bash
python scripts/validate_paper_trading.py
```

Expected output:
```
✅ Database initialized with WAL mode
✅ Cycle completed in 250ms
✅ Paper trade executed (Trade ID: 1)
✅ Trade persisted in database (Status: open)
ALL VALIDATIONS PASSED ✅
```

---

## 📡 API Usage Examples

### Execute Paper Trade Cycle

**cURL**:
```bash
curl -X POST "http://localhost:8000/api/v1/paper-trading/run-cycle" \
  -H "Authorization: Bearer my_secure_secret_123" \
  -H "Content-Type: application/json" \
  -d '{
    "market_data": {
      "symbol": "BTC/USDT",
      "current_price": 45000.0,
      "volume_24h": 25000000000,
      "volatility": 0.45,
      "rsi": 55.0,
      "macd": 150.0
    },
    "user_id": "trader_001"
  }'
```

**Python**:
```python
import httpx
import asyncio

async def execute_trade():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/paper-trading/run-cycle",
            headers={"Authorization": "Bearer my_secure_secret_123"},
            json={
                "market_data": {
                    "symbol": "BTC/USDT",
                    "current_price": 45000.0,
                    "volatility": 0.45
                },
                "user_id": "trader_001"
            }
        )
        return response.json()

trade = asyncio.run(execute_trade())
print(f"Trade ID: {trade['trade']['trade_id']}")
```

**Response**:
```json
{
  "status": "success",
  "trade": {
    "trade_id": 1,
    "symbol": "BTC/USDT",
    "side": "LONG",
    "entry_price": 45000.0,
    "qty": 0.0189,
    "leverage": 2,
    "stop_loss": 44100.0,
    "take_profit": 46800.0
  },
  "ai_analysis": {
    "regime": "Normal",
    "strategy": "momentum",
    "confidence": 0.85
  }
}
```

---

### Close Paper Trade

**cURL**:
```bash
curl -X POST "http://localhost:8000/api/v1/paper-trading/close-trade/1?exit_price=47250.0" \
  -H "Authorization: Bearer my_secure_secret_123"
```

**Response**:
```json
{
  "status": "success",
  "trade": {
    "trade_id": 1,
    "symbol": "BTC/USDT",
    "side": "LONG",
    "entry_price": 45000.0,
    "exit_price": 47250.0,
    "profit": 85.0,
    "profit_pct": 10.0
  }
}
```

---

### View Open Trades

**cURL**:
```bash
curl -X GET "http://localhost:8000/api/v1/paper-trading/open-trades?user_id=trader_001" \
  -H "Authorization: Bearer my_secure_secret_123"
```

---

### View Trade History

**cURL**:
```bash
curl -X GET "http://localhost:8000/api/v1/paper-trading/trade-history?user_id=trader_001&limit=10" \
  -H "Authorization: Bearer my_secure_secret_123"
```

**Response**:
```json
{
  "status": "success",
  "statistics": {
    "total_trades": 5,
    "winning_trades": 3,
    "losing_trades": 2,
    "win_rate_pct": 60.0,
    "total_profit_usd": 250.50,
    "avg_profit_pct": 5.25
  },
  "trades": [...]
}
```

---

## 🤖 Setting Up Telegram Bot

### 1. Create Bot
1. Open Telegram and search for `@BotFather`
2. Send `/newbot`
3. Follow prompts to name your bot
4. Copy the **bot token** (looks like: `1234567890:ABCdef...`)

### 2. Get Chat ID
1. Search for `@userinfobot` in Telegram
2. Send any message
3. Copy your **chat ID** (numeric value)

### 3. Configure
Add to `.env`:
```env
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789
```

### 4. Test
Restart server and execute a trade. You'll receive:
- ✅ Trade entry notification
- ✅ Trade exit notification with P&L

---

## 🎯 Risk Management Rules

The system automatically applies these rules:

### Leverage by Market Regime
- **Low Volatility**: 3x leverage
- **Normal**: 2x leverage
- **High Volatility**: 1x leverage (conservative)

### Stop-Loss & Take-Profit
- **Stop-Loss**: 2% below entry (for LONG)
- **Take-Profit**: 4% above entry (2:1 reward:risk ratio)
- Automatically calculated based on entry price

### Position Sizing
- Based on strategy confidence level
- Higher confidence = larger position
- Max position size from risk assessment

---

## 📊 Monitoring

### Interactive API Docs
Open browser: `http://localhost:8000/docs`

Features:
- Visual API explorer
- Try it out functionality
- Request/response schemas

### Health Check
```bash
curl http://localhost:8000/health
```

Response:
```json
{"status": "healthy"}
```

---

## 🔧 Troubleshooting

### Issue: Module not found errors
**Solution**: Activate virtual environment
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### Issue: Database locked
**Solution**: SQLite WAL mode handles concurrency, but ensure no other process is accessing the DB file.

### Issue: Telegram notifications not working
**Check**:
1. Verify `TELEGRAM_BOT_TOKEN` is correct
2. Verify `TELEGRAM_CHAT_ID` is numeric
3. Ensure bot is not blocked in chat
4. Check server logs for error messages

### Issue: Rate limit exceeded (429)
**Solution**: Wait 60 seconds or increase rate limit in `app/api/trading.py`

---

## 📈 Example Trading Session

```python
import httpx
import asyncio

async def trading_session():
    base_url = "http://localhost:8000/api/v1"
    headers = {"Authorization": "Bearer my_secure_secret_123"}
    
    async with httpx.AsyncClient() as client:
        # 1. Execute trade
        print("Executing trade...")
        response = await client.post(
            f"{base_url}/paper-trading/run-cycle",
            headers=headers,
            json={
                "market_data": {
                    "symbol": "ETH/USDT",
                    "current_price": 3000.0,
                    "volatility": 0.5
                },
                "user_id": "trader_001"
            }
        )
        trade = response.json()
        trade_id = trade['trade']['trade_id']
        print(f"Trade opened: #{trade_id}")
        
        # 2. Simulate price movement and close
        await asyncio.sleep(2)  # Wait 2 seconds
        
        exit_price = 3150.0  # 5% profit
        print(f"Closing trade at ${exit_price}...")
        
        response = await client.post(
            f"{base_url}/paper-trading/close-trade/{trade_id}",
            headers=headers,
            params={"exit_price": exit_price}
        )
        result = response.json()
        
        profit = result['trade']['profit']
        profit_pct = result['trade']['profit_pct']
        print(f"Trade closed! Profit: ${profit:.2f} ({profit_pct:+.2f}%)")
        
        # 3. Check statistics
        response = await client.get(
            f"{base_url}/paper-trading/trade-history",
            headers=headers,
            params={"user_id": "trader_001"}
        )
        stats = response.json()['statistics']
        print(f"\nOverall Stats:")
        print(f"  Total Trades: {stats['total_trades']}")
        print(f"  Win Rate: {stats['win_rate_pct']}%")
        print(f"  Total P&L: ${stats['total_profit_usd']:.2f}")

asyncio.run(trading_session())
```

---

## 🎓 Next Steps

1. **Read Full Documentation**: See `PAPER_TRADING_IMPLEMENTATION.md`
2. **Explore API Docs**: Visit `http://localhost:8000/docs`
3. **Customize Strategies**: Modify `app/ai/orchestrator.py` agent logic
4. **Add More Exchanges**: Extend trading adapters
5. **Enable Live Trading**: Replace paper trades with real exchange API calls

---

## 📞 Support

For issues or questions:
1. Check validation script: `python scripts/validate_paper_trading.py`
2. Review logs for error messages
3. Consult full documentation: `PAPER_TRADING_IMPLEMENTATION.md`

Happy Trading! 🚀
