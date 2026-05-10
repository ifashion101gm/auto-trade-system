# Environment Setup Guide

## 📋 Quick Start

### Step 1: Review Configuration Files

Two environment files have been created:

1. **`.env.example`** - Template with all available options and documentation
2. **`.env`** - Active configuration file (gitignored for security)

### Step 2: Configure Required Settings

Edit the `.env` file and update these **required** values:

#### **Trading API Security** (Required)
```env
TRADING_API_SECRET=generate_a_secure_random_string_here
```

Generate a secure secret:
```bash
openssl rand -hex 32
```

#### **Binance Testnet** (Required for Live Trading)
```env
BINANCE_API_KEY=your_actual_api_key
BINANCE_API_SECRET=your_actual_api_secret
BINANCE_TESTNET=true  # Keep true for safety!
EXECUTION_MODE=semi-auto
```

**Get Binance Testnet API Keys:**
1. Visit: https://testnet.binance.vision/
2. Sign in with GitHub
3. Go to API Management
4. Create new API key
5. Copy API Key and Secret to `.env`

#### **Telegram Notifications** (Recommended)
```env
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789
```

**Setup Telegram Bot:**
1. Message `@BotFather` on Telegram
2. Send `/newbot` and follow prompts
3. Copy the bot token
4. Message `@userinfobot` to get your chat ID
5. Add both to `.env`

#### **LLM Provider** (At least one required)
```env
# Choose at least one:
OPENAI_API_KEY=sk-your-key-here
# OR
ANTHROPIC_API_KEY=sk-ant-your-key-here
# OR
GOOGLE_API_KEY=AIza-your-key-here
```

### Step 3: Verify Configuration

Test that your configuration loads correctly:

```bash
source .venv/bin/activate
python -c "from app.config import settings; print('Config loaded successfully'); print(f'Testnet: {settings.BINANCE_TESTNET}'); print(f'Mode: {settings.EXECUTION_MODE}')"
```

Expected output:
```
Config loaded successfully
Testnet: True
Mode: semi-auto
```

### Step 4: Start the System

```bash
# Activate virtual environment
source .venv/bin/activate

# Initialize database
python migrate.py upgrade

# Start API server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Visit: http://localhost:8000/docs for API documentation

---

## 🔒 Security Best Practices

### ✅ DO:
- Keep `.env` file private (already in `.gitignore`)
- Use strong, random secrets for `TRADING_API_SECRET`
- Start with `BINANCE_TESTNET=true`
- Use minimal position sizes for testing
- Regularly rotate API keys
- Monitor Telegram alerts

### ❌ DON'T:
- Never commit `.env` to version control
- Never share API keys publicly
- Never set `BINANCE_TESTNET=false` without extensive testing
- Never use `EXECUTION_MODE=fully-auto` initially
- Never store mainnet keys in development environment

---

## 🎯 Configuration Options Explained

### Execution Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| `proposal` | AI generates trade ideas only | Strategy validation, backtesting |
| `semi-auto` | AI proposes, you confirm via API | **Recommended for testing** |
| `fully-auto` | AI executes automatically | Production (after thorough testing) |

### Binance Testnet vs Mainnet

| Setting | Purpose | Risk Level |
|---------|---------|------------|
| `BINANCE_TESTNET=true` | Paper money, real market data | ✅ Safe for testing |
| `BINANCE_TESTNET=false` | Real money trading | ⚠️ High risk |

**Always test extensively on testnet before using mainnet!**

---

## 🛠️ Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'pydantic_settings'"
**Solution:**
```bash
pip install pydantic-settings==2.12.0
```

### Issue: "ModuleNotFoundError: No module named 'ccxt'"
**Solution:**
```bash
pip install ccxt==4.5.18
```

### Issue: Configuration not loading
**Solution:**
1. Ensure `.env` file is in project root
2. Check file permissions: `chmod 600 .env`
3. Verify syntax (no spaces around `=`)
4. Restart the application

### Issue: Binance API authentication failed
**Solution:**
1. Verify API keys are correct (no extra spaces)
2. Check API key has trading permissions enabled
3. Ensure you're using testnet keys for testnet
4. Wait a few minutes after creating new API keys

### Issue: Telegram notifications not working
**Solution:**
1. Verify bot token is correct
2. Ensure chat ID is numeric
3. Send a message to your bot first (bots can't initiate)
4. Check bot is not blocked

---

## 📊 Environment Variables Reference

### Required Variables
- `TRADING_API_SECRET` - API authentication
- At least one LLM provider key (OPENAI/ANTHROPIC/GOOGLE)

### For Live Trading
- `BINANCE_API_KEY` - Exchange API key
- `BINANCE_API_SECRET` - Exchange API secret
- `BINANCE_TESTNET` - Testnet flag (default: true)
- `EXECUTION_MODE` - Execution mode (default: semi-auto)

### Optional but Recommended
- `TELEGRAM_BOT_TOKEN` - For trade notifications
- `TELEGRAM_CHAT_ID` - Your Telegram chat ID

### Infrastructure
- `DATABASE_URL` - Database connection (default: SQLite)
- `REDIS_URL` - Redis for caching/rate limiting
- `APP_ENV` - Environment name (development/production)
- `LOG_LEVEL` - Logging verbosity (DEBUG/INFO/WARNING/ERROR)

---

## 🚀 Next Steps

After configuring your environment:

1. ✅ Run database migrations: `python migrate.py upgrade`
2. ✅ Validate configuration: See troubleshooting section
3. ✅ Test with paper trading first: `python scripts/validate_paper_trading.py`
4. ✅ Reset for testnet: Use database reset utility
5. ✅ Test on Binance Testnet: `python scripts/validate_binance_testnet.py` (to be created)
6. ✅ Monitor via Telegram alerts
7. ✅ Gradually increase automation level

---

## 📞 Support

For issues or questions:
1. Check this guide's troubleshooting section
2. Review logs for error messages
3. Verify all required variables are set
4. Test each component individually

**Remember**: Always start with testnet and proposal/semi-auto modes before moving to live trading!
