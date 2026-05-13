# Trade Rejection Deduplication Implementation

## Overview
Implemented a deduplication mechanism for trade rejection reports to prevent spamming identical Telegram notifications within a short timeframe.

**Updated with Singleton Pattern (May 13, 2026):** Fixed critical issue where multiple `TelegramNotifier` instances had separate deduplication state, causing duplicate notifications. Now uses singleton pattern to ensure global shared state.

## Problem
The system was sending duplicate rejection notifications for trades with identical characteristics (same symbol, quality score, and reason) within seconds of each other.

### Root Cause Analysis
The deduplication logic existed but wasn't working because:
1. **Multiple Independent Instances**: Different parts of the code created NEW `TelegramNotifier()` instances
2. **No Shared State**: Each instance had its own `_rejection_cooldowns` dictionary
3. **Deduplication Only Worked Within Same Instance**: Cooldown tracking failed when different code paths used different notifier instances

**Example of the bug:**
- `[5/13/2026 7:29 PM]` - Symbol: XAU/USDT:USDT, Score: 65/100, Reason: Quality score below threshold at 12:59:01 UTC
- `[5/13/2026 7:29 PM]` - Symbol: XAU/USDT:USDT, Score: 65/100, Reason: Quality score below threshold at 12:59:02 UTC (1 second later!)

Both notifications were sent because `trading_service.py` created a new notifier instance that didn't share cooldown state with the script's notifier.

## Solution

### 1. Singleton Pattern Implementation (`app/notifications/notifier.py`)

Added singleton pattern to ensure all `TelegramNotifier` instances share the same deduplication state:

#### Class-Level Shared State
```python
class TelegramNotifier:
    # Class-level singleton instance and shared deduplication state
    _instance = None
    _shared_rejection_cooldowns: Dict[tuple, datetime] = {}
    
    def __new__(cls, *args, **kwargs):
        """Ensure only one instance exists (singleton pattern)."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
```

#### Modified `__init__` Method
- Added `_initialized` flag to prevent re-initialization
- Changed instance-level `_rejection_cooldowns` to reference class-level `_shared_rejection_cooldowns`
- Ensures all instances point to the same dictionary

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

### 2. Fixed Trading Service Integration (`app/execution/trading_service.py`)

Changed from creating new notifier instance to using existing shared instance:

```python
# Before: Created new instance (no shared state)
from app.notifications.notifier import TelegramNotifier
notifier = TelegramNotifier()
await notifier.send_trade_rejection_report(...)

# After: Use existing instance (singleton ensures shared state)
await self.notifier.send_trade_rejection_report(...)
```

This ensures the trading service's rejection reports benefit from the same deduplication state as scripts and other components.

### 3. Script Compatibility

All existing scripts automatically benefit from the singleton pattern without code changes:
- `scripts/cleanup_and_restart_mexc_cycle.py`
- `scripts/cleanup_and_restart_bybit_demo_cycle.py`
- `scripts/close_mexc_position_and_restart.py`
- `scripts/close_manual_position_and_restart.py`
- And all other scripts using `TelegramNotifier()`

Since they all now get the same singleton instance, deduplication works globally across the entire application.

### 4. Trading Service Integration

Already using `send_trade_rejection_report()` method with the shared notifier instance (fixed in this update).
Automatically benefits from global deduplication.

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

Created comprehensive test suite: `test_notifier_singleton.py`

Tests verify:
1. ✅ Singleton pattern (all instances are the same object)
2. ✅ Shared deduplication state across instances
3. ✅ Cooldown logic (blocks duplicates, allows differences)
4. ✅ Cooldown expiration (allows after timeout)
5. ✅ Reason categorization accuracy
6. ✅ Score range grouping correctness
7. ✅ Memory cleanup (removes old entries)

Run tests:
```bash
source .venv/bin/activate
python test_notifier_singleton.py
```

**Test Results:** All 7 tests passed ✅

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

1. `app/notifications/notifier.py` - Added singleton pattern with shared deduplication state
2. `app/execution/trading_service.py` - Fixed to use existing notifier instance instead of creating new one
3. `test_notifier_singleton.py` - Comprehensive test suite for singleton and deduplication (new file)

## Verification Checklist

- [x] Analyzed notification logic in notifier.py
- [x] Identified root cause: multiple independent notifier instances
- [x] Implemented singleton pattern for global shared state
- [x] Fixed trading_service.py to use shared instance
- [x] Verified all scripts automatically benefit from singleton
- [x] Ensures different reasons/scores still get through
- [x] Created comprehensive test suite (7 tests)
- [x] All tests pass successfully
- [x] Documented behavior and configuration
- [x] Verified fix resolves duplicate notification issue
