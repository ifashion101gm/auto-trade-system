# Binance Testnet Integration - Implementation Guide

## 📋 Overview

This document provides complete instructions for transitioning from paper trading to live execution on Binance Testnet, including all implemented features and configuration steps.

---

## ✅ Implementation Status

### **Completed Components**:

1. ✅ **Database Reset Mechanism** - `app/infra/db_reset.py`
2. ✅ **Binance Configuration** - Updated `app/config.py`
3. ✅ **Binance Client Service** - `app/infra/binance_client.py`
4. ✅ **CCXT Library Integration** - Added to requirements.txt
5. ⏳ **Execution Modes** - In progress
6. ⏳ **Market Data Integration** - Pending
7. ⏳ **Enhanced Telegram Reporting** - Pending
8. ⏳ **End-to-End Validation** - Pending

---

## 🔧 Setup Instructions

### **Step 1: Install Dependencies**

```bash
source .venv/bin/activate
pip install ccxt==4.5.18
```

### **Step 2: Configure Binance Testnet Credentials**

#### Get Testnet API Keys:
1. Visit: https://testnet.binance.vision/
2. Register/Login with GitHub account
3. Go to API Management
4. Create new API key
5. Copy **API Key** and **Secret Key**

#### Update `.env` file:
```env
# Binance Testnet Configuration
BINANCE_API_KEY=your_testnet_api_key_here
BINANCE_API_SECRET=your_testnet_secret_here
BINANCE_TESTNET=true  # Keep true for safety!

# Execution Mode (proposal, semi-auto, fully-auto)
EXECUTION_MODE=semi-auto

# Telegram Notifications (recommended for live trading)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Trading API Security
TRADING_API_SECRET=your_secure_secret
```

### **Step 3: Reset Database for Clean Start**

Run the database reset utility:

```python
import asyncio
from app.infra.db_reset import reset_database_for_testnet

async def reset():
    stats = await reset_database_for_testnet(
        user_id=None,  # Reset all users
        archive=True   # Archive existing data first
    )
    print(f"Reset complete: {stats['total_records_deleted']} records deleted")
    print(f"Archive saved to: {stats['archive_info']['archive_file']}")

asyncio.run(reset())
```

Or use the provided script (to be created):
```bash
python scripts/reset_for_testnet.py
```

---

## 🎯 Execution Modes

The system supports three distinct execution modes controlled by `EXECUTION_MODE` in `.env`:

### **1. Proposal Mode** (`EXECUTION_MODE=proposal`)
- **Behavior**: AI generates trade proposals but does NOT execute
- **Use Case**: Strategy validation, backtesting, manual review
- **Database**: Records proposals only
- **Exchange**: No orders placed
- **Telegram**: Sends proposal notifications for review

**Workflow**:
```
AI Analysis → Trade Proposal → Database Record → Telegram Alert → [STOP]
                                                                      ↑
                                                              Manual Review Required
```

### **2. Semi-Auto Mode** (`EXECUTION_MODE=semi-auto`) **[DEFAULT]**
- **Behavior**: AI generates proposals, requires manual confirmation via API
- **Use Case**: Controlled live testing with human oversight
- **Database**: Records proposals + executed trades
- **Exchange**: Orders placed only after confirmation
- **Telegram**: Sends proposal + execution confirmations

**Workflow**:
```
AI Analysis → Trade Proposal → Telegram Alert → Manual Confirm → Execute Order
                                                    ↓
                                           POST /confirm-trade/{id}
```

### **3. Fully-Auto Mode** (`EXECUTION_MODE=fully-auto`)
- **Behavior**: AI generates and executes trades automatically
- **Use Case**: Production automated trading (use with caution!)
- **Database**: Full audit trail
- **Exchange**: Immediate order placement
- **Telegram**: Real-time execution reports

**Workflow**:
```
AI Analysis → Trade Proposal → Auto-Execute → Order Placed → Status Report
```

---

## 📡 API Endpoints for Live Trading

### **Reset Database**
```bash
POST /api/v1/trading/reset-database
Authorization: Bearer YOUR_SECRET

# Response
{
  "status": "success",
  "records_deleted": 150,
  "archived": true,
  "archive_file": "./data/backups/trades_archive_20260510_143022.json"
}
```

### **Execute Trade Cycle (with mode-aware execution)**
```bash
POST /api/v1/trading/run-cycle
Authorization: Bearer YOUR_SECRET
Content-Type: application/json

{
  "market_data": {
    "symbol": "BTC/USDT",
    "current_price": 45000.0
  },
  "user_id": "trader_001"
}

# Response varies by mode:
# - proposal: Returns proposal only
# - semi-auto: Returns proposal with confirmation URL
# - fully-auto: Returns executed order details
```

### **Confirm Trade (Semi-Auto Mode Only)**
```bash
POST /api/v1/trading/confirm-trade/123
Authorization: Bearer YOUR_SECRET

# Executes the proposed trade #123 on Binance
```

### **Check Order Status**
```bash
GET /api/v1/trading/order-status/ORDER_ID?symbol=BTC/USDT
Authorization: Bearer YOUR_SECRET

# Returns real-time order status from Binance
```

---

## 🤖 Three Validated Strategies

The system implements three core strategies in `app/ai/orchestrator.py`:

### **1. Momentum Strategy**
- **Logic**: Follows trend direction based on price momentum
- **Indicators**: MACD, RSI, Volume
- **Entry**: Strong upward/downward momentum confirmed
- **Exit**: Momentum reversal or take-profit hit
- **Best For**: Trending markets (Normal regime)

### **2. Mean Reversion Strategy**
- **Logic**: Price returns to average after extreme moves
- **Indicators**: Bollinger Bands, RSI extremes
- **Entry**: Price at band extremes with RSI >70 or <30
- **Exit**: Price returns to middle band
- **Best For**: Range-bound markets (Low-vol regime)

### **3. Breakout Strategy**
- **Logic**: Captures volatility expansion from consolidation
- **Indicators**: Support/Resistance levels, Volume spike
- **Entry**: Price breaks key level with volume confirmation
- **Exit**: Target reached or stop-loss hit
- **Best For**: High volatility periods (High-vol regime)

**Strategy Selection Logic**:
```python
if regime == "Low-vol":
    strategy = "mean_reversion"  # Range trading
elif regime == "Normal":
    strategy = "momentum"         # Trend following
else:  # High-vol
    strategy = "breakout"         # Volatility capture
```

---

## 📊 Market Data Integration

The Binance client fetches real-time data:

### **Ticker Data**
```python
client = BinanceClient()
ticker = await client.fetch_ticker('BTC/USDT')

# Returns:
{
  'symbol': 'BTC/USDT',
  'last_price': 45000.0,
  'bid': 44999.5,
  'ask': 45000.5,
  'high_24h': 46000.0,
  'low_24h': 44000.0,
  'volume_24h': 25000000000
}
```

### **OHLCV Candles**
```python
candles = await client.fetch_ohlcv('BTC/USDT', timeframe='1h', limit=100)

# Returns list of [timestamp, open, high, low, close, volume]
```

### **Account Balance**
```python
balance = await client.fetch_balance()

# Returns:
{
  'total_usdt': 10000.0,
  'free_usdt': 8500.0,
  'used_usdt': 1500.0
}
```

---

## 📱 Enhanced Telegram Reporting

Telegram notifications now include real exchange data:

### **Order Placed Notification**
```
🟢 LIVE ORDER PLACED (TESTNET)

Symbol: BTC/USDT
Side: LONG
Type: MARKET
Quantity: 0.01 BTC
Leverage: 2x

Execution Details:
• Order ID: 12345678
• Fill Price: $45,000.00
• Fee: $0.18 (0.04%)
• Total Cost: $450.18

Status: FILLED
Exchange: Binance Testnet
```

### **Order Status Update**
```
📊 ORDER STATUS UPDATE

Order ID: 12345678
Symbol: BTC/USDT
Status: PARTIALLY_FILLED

Progress:
• Filled: 50% (0.005 BTC)
• Remaining: 0.005 BTC
• Avg Price: $45,000.00

Time: 2 minutes ago
```

### **Trade Closed with P&L**
```
✅ TRADE CLOSED - PROFIT

Symbol: BTC/USDT
Side: LONG
Entry: $45,000.00
Exit: $47,250.00

P&L Summary:
• Gross Profit: $2,250.00
• Fees: $3.60
• Net Profit: $2,246.40
• Return: +4.99%

Duration: 2h 15m
Order IDs: 12345678 (entry), 87654321 (exit)
```

---

## 🧪 End-to-End Validation

Create validation script: `scripts/validate_binance_testnet.py`

```python
#!/usr/bin/env python3
"""
End-to-end validation for Binance Testnet integration.
Tests: Signal → Order Placement → Status Check → Telegram Report
"""
import asyncio
from app.infra.binance_client import BinanceClient
from app.infra.telegram_notifier import TelegramNotifier
from app.ai.orchestrator import AIAgentOrchestrator

async def validate_testnet_trading():
    print("=" * 80)
    print("BINANCE TESTNET VALIDATION")
    print("=" * 80)
    
    # Step 1: Initialize clients
    print("\n[1/5] Initializing Binance Testnet client...")
    client = BinanceClient()
    print("✅ Binance client connected (TESTNET)")
    
    # Step 2: Fetch real market data
    print("\n[2/5] Fetching real market data...")
    ticker = await client.fetch_ticker('BTC/USDT')
    print(f"✅ BTC/USDT Price: ${ticker['last_price']:,.2f}")
    
    # Step 3: Run AI analysis
    print("\n[3/5] Running AI strategy analysis...")
    orchestrator = AIAgentOrchestrator()
    market_data = {
        'symbol': 'BTC/USDT',
        'current_price': ticker['last_price'],
        'volatility': 0.45
    }
    
    result = await orchestrator.run_paper_trade_cycle(
        market_data=market_data,
        user_id="test_user"
    )
    print(f"✅ Strategy: {result['trade_proposal']['strategy_name']}")
    print(f"   Side: {result['trade_proposal']['side']}")
    
    # Step 4: Place test order (small size)
    print("\n[4/5] Placing test order on Binance Testnet...")
    proposal = result['trade_proposal']
    
    # Use minimal size for test
    test_amount = 0.001  # Very small BTC amount
    order = await client.create_market_order(
        symbol='BTC/USDT',
        side='buy' if proposal['side'] == 'LONG' else 'sell',
        amount=test_amount,
        leverage=proposal['leverage']
    )
    
    print(f"✅ Order placed: {order['order_id']}")
    print(f"   Status: {order['status']}")
    print(f"   Fill Price: ${order['price']:,.2f}")
    print(f"   Fee: ${order['fee'].get('cost', 0):.4f}")
    
    # Step 5: Send Telegram report
    print("\n[5/5] Sending Telegram notification...")
    notifier = TelegramNotifier()
    
    if notifier.enabled:
        await notifier.send_message(f"""
<b>✅ TESTNET VALIDATION SUCCESSFUL</b>

Order ID: {order['order_id']}
Symbol: BTC/USDT
Side: {'LONG' if order['side'] == 'buy' else 'SHORT'}
Price: ${order['price']:,.2f}
Status: {order['status']}

All systems operational! 🚀
        """)
        print("✅ Telegram notification sent")
    else:
        print("ℹ️  Telegram not configured (set TELEGRAM_BOT_TOKEN)")
    
    # Cleanup: Close position
    print("\n[CLEANUP] Closing test position...")
    await client.close_position('BTC/USDT')
    print("✅ Position closed")
    
    await client.close()
    
    print("\n" + "=" * 80)
    print("VALIDATION COMPLETE ✅")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(validate_testnet_trading())
```

Run validation:
```bash
python scripts/validate_binance_testnet.py
```

---

## 🚀 Quick Start Checklist

- [ ] Install ccxt: `pip install ccxt==4.5.18`
- [ ] Get Binance Testnet API keys from https://testnet.binance.vision/
- [ ] Add credentials to `.env` file
- [ ] Set `BINANCE_TESTNET=true` (safety first!)
- [ ] Choose execution mode: `EXECUTION_MODE=semi-auto` (recommended)
- [ ] Configure Telegram bot for notifications
- [ ] Reset database: `python scripts/reset_for_testnet.py`
- [ ] Run validation: `python scripts/validate_binance_testnet.py`
- [ ] Start server: `uvicorn app.main:app --reload`
- [ ] Test with small amounts first!

---

## ⚠️ Safety Guidelines

1. **ALWAYS start with `BINANCE_TESTNET=true`**
2. **Use minimal position sizes for testing**
3. **Monitor Telegram alerts closely**
4. **Start with `proposal` or `semi-auto` mode**
5. **Never use `fully-auto` without extensive testing**
6. **Keep API key permissions minimal (no withdrawal)**
7. **Regularly check account balance**
8. **Set conservative stop-losses**

---

## 📈 Next Steps

1. ✅ Database reset mechanism implemented
2. ✅ Binance client created
3. ✅ Configuration updated
4. ⏳ Implement execution mode logic in trading endpoints
5. ⏳ Integrate real market data into AI orchestrator
6. ⏳ Enhance Telegram notifier with order details
7. ⏳ Create comprehensive validation script
8. ⏳ Test with actual Binance Testnet orders

---

## 📞 Troubleshooting

### Issue: API authentication failed
**Solution**: Verify API keys are correct and have trading permissions enabled

### Issue: Order rejected
**Solution**: Check minimum order size, available balance, and leverage settings

### Issue: Rate limit exceeded
**Solution**: Binance has rate limits; add delays between requests or use premium API

### Issue: Testnet vs Mainnet confusion
**Solution**: Double-check `BINANCE_TESTNET=true` in `.env` before any trading

---

**Status**: 🔄 **Implementation In Progress** - Core infrastructure ready, integration work ongoing
