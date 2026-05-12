# TradingView Webhook Quick Reference

## Quick Start

### 1. Configure Environment
```bash
# Add to .env file
TRADING_API_SECRET=my_super_secret_key_123
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
EXECUTION_MODE=fully-auto
```

### 2. Apply Database Migration
```bash
cd /home/admin/.openclaw/workspace/auto-trade-system
alembic upgrade head
```

### 3. Test the Endpoint
```bash
python scripts/test_tradingview_webhook.py
```

### 4. Configure TradingView Alert

**Webhook URL:**
```
https://your-domain.com/api/webhooks/tradingview
```

**Headers:**
```
Authorization: Bearer my_super_secret_key_123
```

**Message Body (JSON):**
```json
{
  "symbol": "{{ticker}}",
  "side": "{{strategy.order.action}}",
  "price": "{{close}}",
  "quantity": 0.01,
  "stop_loss": {{strategy.order.stop_price}},
  "take_profit": {{strategy.order.take_profit}},
  "leverage": 2,
  "confidence": 0.8
}
```

## Supported Formats

### Symbols
| Input | Normalized To |
|-------|---------------|
| `BTCUSDT` | `BTC/USDT` |
| `ETH/USDT` | `ETH/USDT` |
| `BTCUSDT.P` | `BTC/USDT` |
| `XAUUSD` | `XAU/USD` |

### Sides
| Input | Mapped To |
|-------|-----------|
| `buy` | `LONG` |
| `long` | `LONG` |
| `sell` | `SHORT` |
| `short` | `SHORT` |

## Required Fields
- `symbol`: Trading pair (e.g., "BTCUSDT")
- `side`: Direction ("buy", "sell", "long", "short")
- `price`: Entry price (must be > 0)
- `quantity`: Position size (must be > 0)

## Optional Fields
- `stop_loss`: Stop loss price
- `take_profit`: Take profit price
- `leverage`: Leverage multiplier (default: 1)
- `confidence`: Signal confidence 0-1 (default: 0.7)
- `strategy`: Strategy name (default: "tradingview_manual")
- `user_id`: User identifier (default: "tradingview_user")

## Execution Modes

### fully-auto
All signals execute immediately after passing risk checks.

### semi-auto
- Position ≤ $100: Auto-execute
- Position > $100: Save as proposal, requires confirmation

### proposal
All signals saved as proposals, require manual confirmation.

## Response Codes

| Code | Meaning |
|------|---------|
| 200 | Success (executed/proposal/rejected) |
| 400 | Invalid payload |
| 401 | Invalid authentication |
| 429 | Rate limit exceeded |
| 500 | Server error |

## Telegram Notifications

You'll receive notifications for:
- ✅ Signal received
- 🚫 Risk engine rejection
- ⏸️ Proposal created
- 📈 Trade executed
- 🚨 Processing errors

## Troubleshooting

### "Invalid TradingView alert: Missing required field"
Check that your JSON includes all required fields: symbol, side, price, quantity

### "401 Unauthorized"
Verify your Authorization header matches TRADING_API_SECRET in .env

### "Rate limit exceeded"
Wait 60 seconds or increase rate limit in config

### "Risk Engine rejection"
Check your portfolio limits, daily P&L, and position sizes

## Example cURL Test

```bash
curl -X POST http://localhost:8000/api/webhooks/tradingview \
  -H "Authorization: Bearer my_super_secret_key_123" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDT",
    "side": "buy",
    "price": 50000.0,
    "quantity": 0.01,
    "stop_loss": 49000.0,
    "take_profit": 52000.0,
    "leverage": 2,
    "confidence": 0.85
  }'
```

## Monitoring

### Check Logs
```bash
# Watch for webhook activity
tail -f logs/app.log | grep "TradingView"
```

### Query Database
```sql
-- Recent TradingView signals
SELECT id, symbol, signal_type, processed, timestamp 
FROM signals 
WHERE source = 'TRADINGVIEW_WEBHOOK' 
ORDER BY timestamp DESC 
LIMIT 10;

-- Unprocessed signals
SELECT * FROM signals WHERE processed = 0;

-- Rejected signals
SELECT * FROM signals WHERE processed = 2;
```

## Security Best Practices

1. Use a strong, unique TRADING_API_SECRET
2. Enable HTTPS in production
3. Rotate secrets periodically
4. Monitor for unusual webhook patterns
5. Set appropriate rate limits
6. Review Telegram notifications regularly

## Support

For issues or questions:
1. Check logs: `logs/app.log`
2. Review this quick reference
3. See full documentation: `TRADINGVIEW_WEBHOOK_IMPLEMENTATION.md`
4. Run test suite: `python scripts/test_tradingview_webhook.py`
