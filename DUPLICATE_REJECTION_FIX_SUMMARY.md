# Duplicate Rejection Notifications Fix - May 13, 2026

## Issue Summary

Duplicate "Trade Proposal REJECTED" Telegram notifications were being sent for identical trade opportunities within 1-second intervals.

**Example from logs:**
- `[5/13/2026 7:29 PM]` - XAU/USDT:USDT, Score: 65/100 at 12:59:01 UTC
- `[5/13/2026 7:29 PM]` - XAU/USDT:USDT, Score: 65/100 at 12:59:02 UTC (1 second later!)

## Root Cause

The deduplication logic in `app/notifications/notifier.py` was correctly implemented but **not working** because:

1. **Multiple Independent Instances**: Different parts of the code created separate `TelegramNotifier()` instances
   - Scripts like `cleanup_and_restart_mexc_cycle.py` created their own instance in `__init__`
   - `trading_service.py` created another instance when sending rejection reports
   - Each instance had its own empty `_rejection_cooldowns` dictionary

2. **No Shared State**: The deduplication cooldown tracking only worked within a single instance
   - When script's notifier recorded a rejection, trading_service's notifier couldn't see it
   - Result: Both sent notifications for the same rejection

## Solution Implemented

### 1. Singleton Pattern in `app/notifications/notifier.py`

Added class-level singleton to ensure all `TelegramNotifier()` calls return the same instance:

```python
class TelegramNotifier:
    # Class-level shared state
    _instance = None
    _shared_rejection_cooldowns: Dict[tuple, datetime] = {}
    
    def __new__(cls, *args, **kwargs):
        """Ensure only one instance exists (singleton pattern)."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, bot_token=None, chat_id=None):
        # Only initialize once
        if hasattr(self, '_initialized'):
            return
        
        # Use SHARED deduplication tracking
        self._rejection_cooldowns = self._shared_rejection_cooldowns
        # ... rest of initialization
        self._initialized = True
```

**Benefits:**
- All code paths now share the same `_rejection_cooldowns` dictionary
- Deduplication works globally across the entire application
- No changes needed in existing scripts (they automatically get the singleton)

### 2. Fixed `app/execution/trading_service.py`

Changed from creating new notifier to using existing shared instance:

```python
# Before (WRONG - created new instance)
from app.notifications.notifier import TelegramNotifier
notifier = TelegramNotifier()
await notifier.send_trade_rejection_report(...)

# After (CORRECT - uses shared singleton instance)
await self.notifier.send_trade_rejection_report(...)
```

## Testing

Created comprehensive test suite (`test_notifier_singleton.py`) with 7 tests:

1. ✅ Singleton pattern verification (all instances are same object)
2. ✅ Shared deduplication state across instances
3. ✅ Deduplication prevents duplicate notifications
4. ✅ Cooldown expiration works correctly
5. ✅ Reason categorization accuracy
6. ✅ Score range grouping correctness
7. ✅ Memory cleanup of old entries

**All tests passed successfully.**

Run tests:
```bash
source .venv/bin/activate
python test_notifier_singleton.py
```

## Impact

### What Gets Suppressed Now ✅
Reports with **ALL** matching within 10 minutes:
1. Same trading symbol (e.g., XAU/USDT:USDT)
2. Same reason category (e.g., quality_threshold)
3. Same score range (e.g., 60-69)

### What Still Gets Through ✅
- Different symbols (XAU/USDT vs PAXG/USDT)
- Different rejection reasons (quality vs confidence vs risk)
- Significantly different quality scores (65 vs 85 = different ranges)
- Same characteristics after cooldown expires (>10 minutes)

### Example Scenarios

**Scenario 1: Duplicate Suppression ✅ (FIXED)**
```
7:29:01 PM - XAU/USDT:USDT, Score 65, "Quality score below threshold" → SENT
7:29:02 PM - XAU/USDT:USDT, Score 65, "Quality score below threshold" → SUPPRESSED ✅
```

**Scenario 2: Different Symbol Allowed ✅**
```
7:29:01 PM - XAU/USDT:USDT, Score 65, "Quality score below threshold" → SENT
7:29:02 PM - PAXG/USDT, Score 65, "Quality score below threshold" → SENT
```

**Scenario 3: Different Reason Allowed ✅**
```
7:29:01 PM - XAU/USDT:USDT, Score 65, "Quality score below threshold" → SENT
7:29:02 PM - XAU/USDT:USDT, Score 65, "Low confidence in signal" → SENT
```

## Files Modified

1. **`app/notifications/notifier.py`**
   - Added singleton pattern with `_instance` and `_shared_rejection_cooldowns`
   - Modified `__new__` to return same instance
   - Modified `__init__` to use shared state and prevent re-initialization

2. **`app/execution/trading_service.py`**
   - Removed redundant `TelegramNotifier()` instantiation in rejection handler
   - Changed to use existing `self.notifier` instance

3. **`test_notifier_singleton.py`** (NEW)
   - Comprehensive test suite verifying singleton and deduplication behavior

4. **`REJECTION_DEDUPLICATION_IMPLEMENTATION.md`**
   - Updated documentation with root cause analysis and fix details

## Verification

The fix has been verified to:
- ✅ Prevent duplicate notifications for identical rejections
- ✅ Allow legitimate variations (different symbols/reasons/scores)
- ✅ Work across all components (scripts, trading service, etc.)
- ✅ Maintain backward compatibility (no breaking changes)
- ✅ Include automatic memory cleanup to prevent leaks

## Configuration

Cooldown period can be adjusted in `app/notifications/notifier.py`:

```python
self._rejection_cooldown_seconds = 600  # Default: 10 minutes
```

Recommended values:
- **5 minutes (300s)**: Aggressive deduplication
- **10 minutes (600s)**: Balanced (current default) ✅
- **15 minutes (900s)**: Conservative

## Conclusion

The duplicate notification issue has been completely resolved by implementing a singleton pattern that ensures global shared deduplication state across all `TelegramNotifier` instances. The fix is minimal, non-breaking, and thoroughly tested.
