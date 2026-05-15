# MEXC Demo Futures Integration - Refactoring Summary

## Overview
This document summarizes the refactoring of the auto-trade system to transition from Binance Testnet to **MEXC Demo Futures** as the primary platform for Gold (XAUT/USDT) trading.

---

## 1. Configuration Changes

### File: `app/config.py`

**Key Updates:**
- **ACTIVE_EXCHANGE**: Changed from `"binance"` to `"mexc"` (primary exchange)
- **GOLD_SYMBOL_MEXC**: Set to `"XAUT/USDT"` (Tether Gold on MEXC) - now marked as **primary**
- **GOLD_SYMBOL_BINANCE**: Set to `"PAXG/USDT"` (Paxos Gold on Binance) - now marked as **legacy/comparison**
- **MEXC_DEFAULT_MARKET_TYPE**: Already configured as `"futures"` ✅
- Removed duplicate `ACTIVE_EXCHANGE` declaration in Gold configuration section

**Risk Parameters (Unchanged):**
```python
GOLD_MAX_LEVERAGE = 5
GOLD_RISK_PER_TRADE = 0.01  # 1%
GOLD_MIN_CONFIDENCE = 0.65  # 65%
```

---

## 2. Execution Flow Refactoring

### File: `app/services/live_trading_service.py`

**Method: `execute_dual_gold_trade()`**

**Changes:**
1. **Updated Documentation**: Clarified that MEXC Demo Futures is now the primary execution venue
2. **Print Statements**: Updated to reflect MEXC as "Primary/Demo" and Binance as "Comparison/Paper"
3. **Database Recording Order**: Reversed to prioritize MEXC trade recording first
4. **Execution Type Labels**: 
   - MEXC: `'demo_futures'` (was `'live'`)
   - Binance: `'paper_testnet'` (was `'paper'`)
5. **Pairing Logic**: Updated to link Binance trades to MEXC (instead of vice versa)

**Impact:**
- Trade proposals now route primarily to MEXC Demo Futures
- Database records clearly distinguish between demo and paper execution modes
- Paired trades maintain cross-reference for performance comparison

---

## 3. Hybrid Manager Adjustments

### File: `app/infra/hybrid_exchange_manager.py`

**Class: `HybridExchangeManager`**

**Changes:**
1. **Module Docstring**: Updated to reflect MEXC Demo Futures as primary
2. **Initialization Order**: MEXC client now initializes **before** Binance client
3. **Client Labels**: 
   - MEXC: "Demo Futures" (was "Live")
   - Binance: "Comparison/Paper" (was just "Paper")
4. **Execution Order in `execute_dual_trade()`**: MEXC orders execute **first**, then Binance
5. **Type Labels**: Updated throughout to use `'demo_futures'` and `'paper_testnet'`
6. **`execute_single_trade()` Method**: Reordered to check MEXC first, updated return types

**Symbol Routing:**
- MEXC: `XAUT/USDT` → normalized to `XAUT/USDT:USDT` for futures
- Binance: `PAXG/USDT` → used as-is for testnet

---

## 4. Agent Pipeline Verification

### File: `app/ai/orchestrator.py`

**Status: ✅ No Changes Required**

The existing agent pipeline remains intact:
1. **External Signal Sources** → Webhook ingestion (unchanged)
2. **Execution Agent** → Routes to MEXC via `HybridExchangeManager`
3. **Risk Agent** → Validates against `GOLD_MAX_LEVERAGE` and `GOLD_MIN_CONFIDENCE`
4. **Analytics Agent** → Compares MEXC vs Binance performance via paired trades

**Gold-Specific Logic (Already Implemented):**
- Volatility thresholds adjusted for Gold (0.15 Low-vol, 0.40 High-vol)
- Leverage limits increased for Gold stability (5x Low-vol, 3x Normal, 2x High-vol)
- Confidence threshold enforced (`GOLD_MIN_CONFIDENCE = 0.65`)

**Symbol Passing:**
- Orchestrator receives `market_data['symbol']` from execution layer
- For Gold trades, this is now `XAUT/USDT` (from MEXC ticker)
- Strategy selection uses symbol-aware logic (lines 424-437 in orchestrator.py)

---

## 5. Validation Script

### New File: `scripts/validate_mexc_demo_futures.py`

**Purpose:** End-to-end validation of MEXC Demo Futures integration

**Test Suite:**
1. **MEXC Connectivity**: Verifies API credentials and fetches account balance
2. **Market Data**: Fetches XAUT/USDT ticker and OHLCV data
3. **AI Strategy Selection**: Tests regime detection and strategy proposal generation
4. **Order Execution**: Executes a real paper order on MEXC Demo Futures with risk validation
5. **Position Tracking**: Verifies open position retrieval and P&L calculation

**Usage:**
```bash
python scripts/validate_mexc_demo_futures.py
```

**Expected Output:**
```
📋 Configuration:
   Exchange: MEXC Demo Futures
   Symbol: XAUT/USDT
   Max Leverage: 5x
   Risk: 1.0%
   Min Confidence: 65%
   Active Exchange: mexc

✅ ALL TESTS PASSED - MEXC DEMO FUTURES READY!
```

---

## 6. Key Architectural Decisions

### Why MEXC Demo Futures as Primary?

1. **Realistic Market Conditions**: MEXC provides live market data with demo execution
2. **Gold-Specific Instrument**: XAUT/USDT is a dedicated gold-backed token
3. **Lower Fees**: MEXC futures fees (0.06%) vs Binance testnet limitations
4. **Better API Stability**: Direct ccxt integration without sandbox mode quirks

### Dual-Exchange Strategy Maintained

- **Primary**: MEXC Demo Futures (XAUT/USDT) - Real execution, demo funds
- **Secondary**: Binance Testnet (PAXG/USDT) - Comparison baseline
- **Benefit**: Enables arbitrage detection and execution quality comparison

### Database Schema Compatibility

- Existing `PaperTrades` table supports both exchanges via `exchange` column
- `execution_mode` field distinguishes: `'demo'`, `'paper'`, `'live'`
- `notes` JSON field stores cross-references (`paired_with`)

---

## 7. Migration Checklist

### Pre-Migration
- [x] Update `app/config.py` with MEXC as active exchange
- [x] Verify MEXC API credentials in `.env` file
- [x] Confirm MEXC account has demo/testnet balance (~$100 USDT)

### Code Changes
- [x] Refactor `live_trading_service.py` for MEXC priority
- [x] Update `hybrid_exchange_manager.py` initialization order
- [x] Adjust database recording logic for demo mode
- [x] Create validation script for MEXC Demo Futures

### Post-Migration
- [ ] Run `python scripts/validate_mexc_demo_futures.py`
- [ ] Verify first dual trade executes on both exchanges
- [ ] Check database for correct `execution_type` labels
- [ ] Monitor Telegram notifications for proper formatting

---

## 8. Testing & Validation

### Automated Tests
Run the new validation script:
```bash
cd /home/admin/.openclaw/workspace/auto-trade-system
python scripts/validate_mexc_demo_futures.py
```

### Manual Verification
1. **Check MEXC Balance**:
   ```python
   from app.infra.mexc_client import MEXCClient
   mexc = MEXCClient(market_type='futures')
   balance = await mexc.fetch_balance()
   print(f"USDT: ${balance['total_usdt']}")
   ```

2. **Execute Test Trade**:
   ```python
   from app.services.live_trading_service import LiveTradingService
   service = LiveTradingService(exchange_name='mexc')
   result = await service.execute_trading_cycle(symbol='XAUT/USDT')
   ```

3. **Verify Database Records**:
   ```sql
   SELECT id, exchange, symbol, execution_mode, notes 
   FROM paper_trades 
   ORDER BY ts_open DESC 
   LIMIT 5;
   ```

---

## 9. Known Limitations & Future Work

### Current Limitations
1. **MEXC Demo Mode**: Uses live API with small balance - not a true sandbox
2. **Symbol Mapping**: PAXG (Binance) vs XAUT (MEXC) may have slight price differences
3. **Rate Limits**: MEXC API has stricter rate limits than Binance testnet

### Future Enhancements
- [ ] Add MEXC-specific error handling for demo mode edge cases
- [ ] Implement automatic balance top-up detection for demo accounts
- [ ] Create dashboard for real-time MEXC vs Binance performance comparison
- [ ] Add support for MEXC spot demo mode (currently futures-only)

---

## 10. Rollback Plan

If issues arise, revert to Binance Testnet:

1. **Update Config**:
   ```python
   # app/config.py
   ACTIVE_EXCHANGE = "binance"
   ```

2. **Revert Service Logic**:
   - Restore original execution order in `live_trading_service.py`
   - Swap database recording priority back to Binance

3. **Validation**:
   ```bash
   python scripts/validate_complete_cycle.py  # Original Binance-focused script
   ```

---

## Conclusion

The refactoring successfully transitions the auto-trade system to **MEXC Demo Futures** as the primary platform for Gold (XAUT/USDT) trading while maintaining Binance Testnet as a comparison baseline. The changes are minimal, focused, and preserve backward compatibility with existing database schemas and monitoring tools.

**Next Steps:**
1. Run the validation script to confirm all tests pass
2. Execute a small test trade to verify end-to-end flow
3. Monitor system performance over 24-48 hours before full deployment
