# Trade Rejection Deduplication Implementation

## Overview
Implemented a deduplication mechanism for trade rejection reports to prevent spamming identical Telegram notifications within a short timeframe.

## Problem
The system was sending duplicate rejection notifications for trades with identical characteristics (same symbol, quality score, and reason) within seconds of each other.

**Example:**
- `[5/13/2026 1:02 AM]` - Symbol: PAXG/USDT, Score: 75/100, Reason: Quality score below threshold
- `[5/13/2026 1:03 AM]` - Symbol: PAXG/USDT, Score: 75/100, Reason: Quality score below threshold (~13 seconds later)

## Solution

### 1. Core Implementation (`app/notifications/notifier.py`)

Added deduplication logic to the `TelegramNotifier` class:

#### New Attributes
- `_rejection_cooldowns`: Dictionary tracking recent rejections by key `(symbol, reason_category, score_range)`
- `_rejection_cooldown_seconds`: Cooldown period (default: 600 seconds / 10 minutes)

#### New Methods

**`_get_reason_category(reason: str) -> str`**
- Normalizes rejection reasons into categories
- Groups similar reasons while distinguishing different issues
- Categories: `quality_threshold`, `confidence_low`, `risk_exceeded`, `volatility_high`, `liquidity_insufficient`, `spread_too_wide`, etc.

**`_get_score_range(quality_score: int) -> str`**
- Groups quality scores into ranges (e.g., "70-79", "80-89")
- Prevents near-duplicate notifications for slightly different scores
- Allows legitimate variations while catching exact duplicates

**`_should_send_rejection(symbol, reason, quality_score) -> bool`**
- Checks if a rejection report should be sent based on cooldown rules
- Returns `False` if an identical report was sent within the cooldown period
- Logs suppression message when blocking duplicates

**`_record_rejection(symbol, reason, quality_score)`**
- Records a rejection for deduplication tracking
- Automatically cleans up old entries to prevent memory leaks

**`_cleanup_old_cooldowns(now: datetime)`**
- Removes expired cooldown entries (older than 2x cooldown period)
- Prevents memory leaks from accumulated tracking data

#### Modified Method
**`send_trade_rejection_report(symbol, reason, quality_score, cycle_time_ms)`**
- Now checks deduplication before sending
- Only records successful sends for tracking
- Returns `False` if suppressed by cooldown

### 2. Script Updates

Fixed incorrect imports and updated to use deduplication-aware method:

#### Fixed Imports (from `app.infra.telegram_notifier` → `app.notifications.notifier`)
- `scripts/cleanup_and_restart_mexc_cycle.py`
- `scripts/close_mexc_position_and_restart.py`
- `scripts/execute_complete_gold_cycle.py`
- `scripts/execute_gold_trade.py`
- `scripts/validate_complete_system.py`
- `scripts/test_trade_validation.py`
- `scripts/validate_paper_trading.py`
- `scripts/validate_production_readiness.py`
- `scripts/monitor_deployment.py`
- `scripts/validate_gold_futures_e2e.py`
- `app/dashboard/trading_api.py`

#### Updated Rejection Handling
**`scripts/cleanup_and_restart_mexc_cycle.py`**
- Changed from direct `send_message()` call to `send_trade_rejection_report()`
- Now benefits from automatic deduplication
- Logs whether report was sent or suppressed

```python
# Before: Manual message construction and sending
message = f"{emoji} <b>Trade Proposal REJECTED...</b>"
await self.notifier.send_message(message)

# After: Use deduplication-aware method
sent = await self.notifier.send_trade_rejection_report(
    symbol=settings.GOLD_SYMBOL_MEXC,
    reason=reason,
    quality_score=quality_score,
    cycle_time_ms=cycle_time
)
if sent:
    logger.info("✅ Sent quality filter rejection report")
else:
    logger.info("⚠️  Rejection report suppressed (deduplication cooldown)")
```

### 3. Trading Service Integration

**`app/execution/trading_service.py`**
- Already using `send_trade_rejection_report()` method
- Automatically benefits from deduplication (no code changes needed)

## Behavior

### What Gets Suppressed
Reports with **ALL** of the following matching within 10 minutes:
1. Same trading symbol (e.g., PAXG/USDT)
2. Same reason category (e.g., quality_threshold)
3. Same score range (e.g., 70-79)

### What Still Gets Through
- Different symbols (PAXG/USDT vs XAUT/USDT)
- Different rejection reasons (quality vs confidence vs risk)
- Significantly different quality scores (75 vs 85 = different ranges)
- Same characteristics after cooldown expires (>10 minutes)

### Example Scenarios

**Scenario 1: Duplicate Suppression ✅**
```
1:02 AM - PAXG/USDT, Score 75, "Quality score below threshold" → SENT
1:03 AM - PAXG/USDT, Score 75, "Quality score below threshold" → SUPPRESSED
```

**Scenario 2: Different Symbol Allowed ✅**
```
1:02 AM - PAXG/USDT, Score 75, "Quality score below threshold" → SENT
1:03 AM - XAUT/USDT, Score 75, "Quality score below threshold" → SENT
```

**Scenario 3: Different Reason Allowed ✅**
```
1:02 AM - PAXG/USDT, Score 75, "Quality score below threshold" → SENT
1:03 AM - PAXG/USDT, Score 75, "Low confidence in signal" → SENT
```

**Scenario 4: Different Score Range Allowed ✅**
```
1:02 AM - PAXG/USDT, Score 75, "Quality score below threshold" → SENT
1:03 AM - PAXG/USDT, Score 85, "Quality score below threshold" → SENT
```

**Scenario 5: After Cooldown Expires ✅**
```
1:02 AM - PAXG/USDT, Score 75, "Quality score below threshold" → SENT
1:13 AM - PAXG/USDT, Score 75, "Quality score below threshold" → SENT (11 min later)
```

## Testing

Created test script: `test_rejection_dedup.py`

Tests verify:
1. ✅ Reason categorization accuracy
2. ✅ Score range grouping correctness
3. ✅ Cooldown logic (blocks duplicates, allows differences)
4. ✅ Cooldown expiration (allows after timeout)
5. ✅ Memory cleanup (removes old entries)

Run tests:
```bash
python test_rejection_dedup.py
```

## Configuration

Cooldown period can be adjusted in `app/notifications/notifier.py`:

```python
self._rejection_cooldown_seconds = 600  # Default: 10 minutes
```

Recommended values:
- **5 minutes (300s)**: Aggressive deduplication
- **10 minutes (600s)**: Balanced (current default)
- **15 minutes (900s)**: Conservative

## Benefits

1. **Reduced Notification Spam**: Eliminates duplicate alerts for same issue
2. **Better Signal-to-Noise Ratio**: Users see meaningful variations
3. **Memory Efficient**: Automatic cleanup prevents accumulation
4. **Flexible**: Distinguishes between truly different rejections
5. **Transparent**: Logs when reports are suppressed

## Impact

- **No Breaking Changes**: Existing code continues to work
- **Backward Compatible**: Method signature unchanged
- **Performance**: Minimal overhead (dictionary lookup)
- **Coverage**: Applies to all rejection reports across system

## Files Modified

1. `app/notifications/notifier.py` - Core deduplication logic
2. `scripts/cleanup_and_restart_mexc_cycle.py` - Import fix + method update
3. Multiple scripts - Import path corrections (11 files total)
4. `test_rejection_dedup.py` - Test suite (new file)

## Verification Checklist

- [x] Analyzed notification logic in notifier.py
- [x] Identified all rejection report triggers
- [x] Implemented deduplication with cooldown
- [x] Ensures different reasons/scores still get through
- [x] Applied to cleanup scripts
- [x] Applied to main trading loop
- [x] Fixed broken imports across codebase
- [x] Created comprehensive test suite
- [x] Documented behavior and configuration
