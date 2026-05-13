# Bybit Demo Cleanup & Restart Script

## Overview

The `cleanup_and_restart_bybit_demo_cycle.py` script automates the complete cleanup and restart procedure for Bybit Demo trading validation cycles. It mirrors the functionality of the MEXC cleanup script but is specifically adapted for the Bybit Demo environment.

## Features

1. **Close Open Trades**: Queries the database for open paper trades on Bybit Demo (XAU/USDT), calculates P&L based on current market prices, and updates their status to 'closed'
2. **Send Closure Reports**: Sends detailed Telegram notifications for each closed trade including entry/exit prices and P&L
3. **Reset Validation State**: Verifies that no open positions remain in the database
4. **Initiate New Cycle**: Uses `LiveTradingService` configured for Bybit Demo to execute a new trading cycle
5. **Send New Trade Report**: Sends Telegram notification with results of the new trade proposal or execution

## Prerequisites

### Environment Configuration

Ensure the following are set in your `.env` file:

```bash
# Bybit Demo Credentials (REQUIRED)
BYBIT_DEMO_API_KEY=your_demo_api_key
BYBIT_DEMO_API_SECRET=your_demo_api_secret
BYBIT_USE_DEMO_DOMAIN=true

# Telegram Notifications (Optional but recommended)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Trading Configuration
ACTIVE_EXCHANGE=bybit
EXECUTION_MODE=semi-auto  # or fully-auto, proposal
TRADING_PROFILE=safer_growth  # or aggressive
```

### Database Setup

- PostgreSQL database must be running
- PaperTrades table must exist with proper schema
- Database connection string configured in `DATABASE_URL`

## Usage

### Basic Execution

```bash
# Activate virtual environment
source .venv/bin/activate

# Run the cleanup and restart procedure
python scripts/cleanup_and_restart_bybit_demo_cycle.py
```

### What Happens During Execution

#### Step 1: Close Open Trades
- Queries database for all open Bybit Demo trades with symbol `XAU/USDT:USDT`
- Fetches current market price via Bybit Demo API
- Calculates P&L for each position
- Updates trade records with exit price, P&L, and closes status
- Commits changes to database

#### Step 2: Send Closure Reports
- For each closed trade, sends a formatted Telegram message including:
  - Trade ID and symbol
  - Entry and exit prices
  - Quantity and leverage
  - P&L (absolute and percentage)
  - Timestamp

#### Step 3: Reset Validation State
- Verifies no open positions remain in database
- Displays summary statistics:
  - Total trades executed
  - Number of closed trades
  - Number of open trades (should be 0)

#### Step 4: Initiate New Cycle
- Creates `LiveTradingService` instance for Bybit Demo
- Executes complete trading cycle for Gold (XAU/USDT:USDT):
  - Fetches market data
  - Runs AI analysis (via OpenRouter if enabled)
  - Generates trade proposal
  - Executes order (based on execution mode)
  - Persists to database

#### Step 5: Send New Trade Report
- Sends Telegram notification with trade details:
  - Market regime and strategy
  - Confidence level
  - Entry price, stop loss, take profit
  - Leverage and execution status
  - Trade/order IDs

## Configuration Details

### Gold Symbol Configuration

The script uses `GOLD_SYMBOL_BYBIT` from `app/config.py`:

```python
GOLD_SYMBOL_BYBIT = "XAU/USDT:USDT"  # Gold perpetual swap on Bybit Demo
```

This follows Bybit's symbol format for perpetual swaps with USDT settlement.

### Exchange Manager Configuration

The script initializes `UnifiedExchangeManager` with:

```python
exchange_manager = UnifiedExchangeManager(
    exchange_name="bybit",
    use_testnet=False  # Bybit Demo doesn't use testnet flag
)
```

**Important**: Bybit Demo uses `demo_trading=True` internally (handled by `BybitClient`), which routes to `api-demo.bybit.com`. The `use_testnet=False` parameter is correct because:
- Testnet → `api-testnet.bybit.com`
- Demo → `api-demo.bybit.com` (requires `demo_trading=True` in BybitClient)

### Live Trading Service Configuration

```python
trading_service = LiveTradingService(
    exchange_name="bybit",
    use_testnet=False,  # Bybit Demo doesn't use testnet
    use_openrouter=True
)
```

The service automatically detects demo mode through the exchange manager and uses appropriate credentials (`BYBIT_DEMO_API_KEY/SECRET`).

## Output Examples

### Successful Execution

```
################################################################################
# BYBIT DEMO TRADING VALIDATION CYCLE - CLEANUP & RESTART
################################################################################
Started at: 2026-05-13 10:30:00 UTC
User ID: default_user
Exchange: Bybit Demo (api-demo.bybit.com)
Symbol: XAU/USDT:USDT

================================================================================
STEP 1: Closing Open Bybit Demo Paper Trades
================================================================================
📊 Found 2 open Bybit Demo trade(s)
   ✅ Closed Trade #123: LONG XAU/USDT:USDT
      Entry: $2,345.67 → Exit: $2,356.89
      P&L: $+0.11 (+0.48%)
   ✅ Closed Trade #124: SHORT XAU/USDT:USDT
      Entry: $2,348.90 → Exit: $2,356.89
      P&L: $-0.08 (-0.34%)

✅ Committed 2 trade closures to database

================================================================================
STEP 2: Sending Closure Reports via Telegram
================================================================================
   ✅ Sent closure report for Trade #123
   ✅ Sent closure report for Trade #124

================================================================================
STEP 3: Resetting Validation State
================================================================================
✅ Validation state reset complete - no open positions
   📊 Total Bybit Demo trades: 15
   📊 Closed trades: 15
   📊 Open trades: 0

================================================================================
STEP 4: Initiating New Validation Cycle
================================================================================
🚀 Starting new trading cycle for XAU/USDT:USDT...
✅ New validation cycle completed successfully

================================================================================
STEP 5: Sending New Trade Report via Telegram
================================================================================
✅ Sent new trade report to Telegram

================================================================================
PROCEDURE COMPLETE
================================================================================
✅ Closed trades: 2
✅ New trade status: success
✅ Completed at: 2026-05-13 10:32:15 UTC

🎉 Cleanup and restart procedure completed successfully!
```

### Quality Filter Rejection

If the AI rejects the trade due to low quality:

```
⚠️  Trade rejected by quality filter
   Quality Score: 62/100
   Reason: Low confidence (0.58 < 0.65 threshold)
   This is normal - system protecting capital from low-quality trades

✅ Sent quality filter rejection report to Telegram
```

## Error Handling

### Common Issues

1. **No Demo API Credentials**
   ```
   ValueError: Demo API credentials required. Set BYBIT_DEMO_API_KEY and BYBIT_DEMO_API_SECRET in .env
   ```
   **Solution**: Generate demo API keys from https://www.bybit.com/en/trade/demo

2. **Database Connection Failed**
   ```
   sqlalchemy.exc.OperationalError: could not connect to server
   ```
   **Solution**: Ensure PostgreSQL is running and `DATABASE_URL` is correct

3. **Telegram Not Configured**
   ```
   Warning: Telegram notifications disabled (no bot token)
   ```
   **Solution**: Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `.env` (optional)

4. **No Open Trades Found**
   ```
   ✅ No open Bybit Demo paper trades found
   ℹ️  No trades to report
   ```
   **Solution**: This is normal if no trades are open. The script will still initiate a new cycle.

## Comparison with MEXC Script

| Feature | MEXC Script | Bybit Demo Script |
|---------|-------------|-------------------|
| Exchange | MEXC Demo Futures | Bybit Demo Trading |
| Symbol | GOLD(XAUT)/USDT | XAU/USDT:USDT |
| Client | MEXCClient | BybitClient (Pybit SDK) |
| Domain | contract.mexc.com | api-demo.bybit.com |
| Testnet Flag | `use_testnet=False` | `use_testnet=False` |
| Demo Mode | Built into MEXC client | `demo_trading=True` in BybitClient |
| Database Exchange Field | `"mexc"` | `"bybit"` |

## Best Practices

1. **Run Before Each Validation Session**: Execute this script before starting a new validation session to ensure clean state

2. **Monitor Telegram Notifications**: Check Telegram for trade reports to verify proper execution

3. **Review Database Records**: After execution, verify trade records in the database:
   ```sql
   SELECT id, symbol, side, status, profit, profit_pct 
   FROM paper_trades 
   WHERE exchange = 'bybit' 
   ORDER BY ts_open DESC 
   LIMIT 10;
   ```

4. **Check Demo Account Balance**: Periodically verify your Bybit Demo account has sufficient virtual funds:
   ```bash
   python scripts/validate_bybit_demo_complete_cycle.py
   ```

5. **Adjust Risk Parameters**: Modify risk settings in `.env` based on your validation goals:
   ```bash
   TRADING_PROFILE=safer_growth  # Conservative
   # or
   TRADING_PROFILE=aggressive    # Higher risk/reward
   ```

## Troubleshooting

### Script Hangs at Step 4

**Possible Causes**:
- API rate limiting
- Network connectivity issues
- Bybit Demo API downtime

**Solutions**:
- Check Bybit Demo status: https://status.bybit.com
- Verify network connectivity
- Reduce frequency of script execution

### Trade Not Executing

**Possible Causes**:
- Quality filter rejection (normal)
- Insufficient balance
- Invalid symbol format

**Solutions**:
- Check quality score in logs
- Verify demo account balance (minimum $100 USDT recommended)
- Confirm symbol format is `XAU/USDT:USDT`

### Database Inconsistencies

**Symptoms**:
- Open trades showing in database but not on exchange
- Missing trade records

**Solutions**:
- Run reconciliation manually:
  ```python
  from app.services.live_trading_service import LiveTradingService
  service = LiveTradingService(exchange_name="bybit", use_testnet=False)
  await service.reconcile_positions(user_id="default_user")
  ```

## Related Scripts

- `scripts/validate_bybit_demo_complete_cycle.py` - Full validation cycle test
- `scripts/test_bybit_demo_order.py` - Simple order placement test
- `scripts/cleanup_and_restart_mexc_cycle.py` - Equivalent script for MEXC
- `scripts/validate_bybit_config.py` - Configuration validation

## Support

For issues or questions:
1. Check logs in `logs/` directory
2. Review Bybit Demo documentation: https://bybit-exchange.github.io/docs/v5/demo
3. Verify environment configuration matches requirements above
