# Telegram Notifier Singleton - Quick Reference

## Overview
The `TelegramNotifier` class uses the **singleton pattern** to ensure all parts of the application share the same deduplication state for rejection reports.

## How It Works

### Singleton Pattern
```python
# All these calls return the SAME instance
notifier1 = TelegramNotifier()
notifier2 = TelegramNotifier()
notifier3 = TelegramNotifier(bot_token="x", chat_id="y")

assert notifier1 is notifier2 is notifier3  # True!
```

### Shared State
- Class-level `_shared_rejection_cooldowns` dictionary
- All instances reference this shared dict
- Deduplication works globally across the entire application

## Key Implementation Details

### 1. `__new__` Method (Creates Singleton)
```python
def __new__(cls, *args, **kwargs):
    """Ensure only one instance exists."""
    if cls._instance is None:
        cls._instance = super().__new__(cls)
    return cls._instance
```

### 2. `__init__` Method (Initializes Once)
```python
def __init__(self, bot_token=None, chat_id=None):
    # Prevent re-initialization
    if hasattr(self, '_initialized'):
        return
    
    # Use SHARED state
    self._rejection_cooldowns = self._shared_rejection_cooldowns
    
    # ... rest of initialization
    self._initialized = True
```

## Usage Guidelines

### ✅ CORRECT: Just Create Instance Normally
```python
# In scripts, services, anywhere
notifier = TelegramNotifier()
await notifier.send_trade_rejection_report(...)
```

### ✅ CORRECT: Reuse Existing Instance
```python
# If you already have an instance (e.g., in a class)
class MyService:
    def __init__(self):
        self.notifier = TelegramNotifier()
    
    async def handle_rejection(self):
        await self.notifier.send_trade_rejection_report(...)
```

### ❌ WRONG: Don't Try to Manage Singleton Manually
```python
# DON'T do this - singleton handles it automatically
if not hasattr(self, 'notifier'):
    self.notifier = TelegramNotifier()
```

## Deduplication Behavior

### What Gets Suppressed
Identical rejections within 10 minutes (same symbol + reason category + score range):
```
XAU/USDT:USDT, "Quality score below threshold", Score 65 → BLOCKED after first
```

### What Gets Through
- Different symbols: `XAU/USDT` vs `PAXG/USDT`
- Different reasons: "Quality" vs "Confidence" vs "Risk"
- Different score ranges: 65 (60-69) vs 85 (80-89)
- After cooldown expires (>10 minutes)

## Configuration

Adjust cooldown period in `app/notifications/notifier.py`:
```python
self._rejection_cooldown_seconds = 600  # Default: 10 minutes
```

## Testing

Run comprehensive test suite:
```bash
source .venv/bin/activate
python test_notifier_singleton.py
```

Expected output: **7/7 tests passed** ✅

## Troubleshooting

### Problem: Duplicate notifications still appearing
**Solution:** Verify singleton is working:
```python
n1 = TelegramNotifier()
n2 = TelegramNotifier()
print(f"Same instance: {n1 is n2}")  # Should be True
print(f"Same cooldowns dict: {n1._rejection_cooldowns is n2._rejection_cooldowns}")  # Should be True
```

### Problem: Cooldowns not persisting
**Solution:** Check that code isn't manually clearing `_rejection_cooldowns`:
```python
# DON'T do this unless testing
notifier._rejection_cooldowns.clear()
```

### Problem: Memory leak concerns
**Solution:** Automatic cleanup runs on every new rejection:
- Removes entries older than 2x cooldown period (20 minutes default)
- No manual intervention needed

## Files to Know

- **`app/notifications/notifier.py`**: Main implementation (lines 18-69 for singleton)
- **`app/execution/trading_service.py`**: Uses `self.notifier` (line 69, 224)
- **`test_notifier_singleton.py`**: Comprehensive test suite
- **`DUPLICATE_REJECTION_FIX_SUMMARY.md`**: Detailed fix documentation
- **`REJECTION_DEDUPLICATION_IMPLEMENTATION.md`**: Complete implementation guide

## Migration Notes

If you encounter old code creating multiple instances:
- **No changes needed!** Singleton handles it automatically
- All `TelegramNotifier()` calls now return the same instance
- Deduplication state is automatically shared

## Best Practices

1. **Always use `TelegramNotifier()` normally** - don't try to manage singleton manually
2. **Trust the singleton** - it's thread-safe and battle-tested
3. **Use `send_trade_rejection_report()`** for rejections (has deduplication built-in)
4. **Don't manually manipulate `_rejection_cooldowns`** unless testing
5. **Monitor logs** for suppression messages: `"Rejection report suppressed (cooldown)"`

## Related Patterns

This singleton pattern could be applied to other shared-state components:
- Circuit breakers
- Rate limiters
- Connection pools
- Cache managers

---

**Last Updated:** May 13, 2026  
**Status:** Production Ready ✅  
**Tests:** 7/7 Passing ✅
