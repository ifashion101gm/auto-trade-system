# Risk Validation Fix - Account-Based Risk Model

## Problem Summary

The trading system was rejecting valid trades due to a **mismatch between position sizing and risk validation**.

### The Issue

**Position Sizing Logic:**
```python
risk_amount = account_balance * risk_per_trade_pct  # e.g., $100 * 2% = $2
quantity = risk_amount / stop_loss_distance
```

**Old Validation Logic (INCORRECT):**
```python
risk_pct = risk_amount / position_value  # e.g., $0.36 / $4.50 = 8%
if risk_pct > threshold:  # 8% > 2% → REJECTED ❌
    reject_trade()
```

This caused small positions to be incorrectly rejected even though they were properly sized according to account risk limits.

### Real-World Example

From the user's issue:
- Account Balance: $100
- Position Value: $4.50 (0.000989 XAU @ $4548)
- Stop Loss Distance: ~$182 (4%)
- Leverage: 2x
- Risk Amount: $0.36

**Old Calculation:**
```
Risk % = $0.36 / $4.50 = 8.00%
Limit: 2%
Result: REJECTED ❌
```

**New Calculation:**
```
Risk % = $0.36 / $100.00 = 0.36%
Limit: 2%
Result: APPROVED ✅
```

## Solution

Changed the validator to use an **account-based risk model** that aligns with how positions are sized.

### Changes Made

#### 1. Updated `TradeValidator` ([app/risk/validator.py](file:///home/admin/.openclaw/workspace/auto-trade-system/app/risk/validator.py))

**Added account_balance parameter:**
```python
async def validate_trade(
    self,
    proposal: Dict[str, Any],
    user_id: str,
    db_session: AsyncSession,
    exchange: str = "mexc",
    symbol: str = "XAUT/USDT",
    account_balance: Optional[float] = None  # NEW
) -> ValidationResult:
```

**Updated risk validation logic:**
```python
async def _validate_risk_per_trade(
    self,
    proposal: Dict[str, Any],
    result: ValidationResult,
    exchange: str,
    symbol: str,
    account_balance: Optional[float] = None  # NEW
):
    """Validate risk per trade against limits.
    
    Uses ACCOUNT-BASED risk model (professional standard):
    - Risk is calculated as percentage of account balance
    - NOT as percentage of position value
    - This ensures consistency with position sizing logic
    """
    # ... calculate risk_amount ...
    
    # CRITICAL FIX: Use account-based risk model
    if account_balance and account_balance > 0:
        # Calculate risk as percentage of ACCOUNT BALANCE
        risk_pct = risk_amount / account_balance
    else:
        # Fallback to position-based if no balance provided
        risk_pct = risk_amount / position_value if position_value > 0 else 0
    
    if risk_pct > threshold:
        # Clear error message showing which model is used
        result.violations.append(...)
```

**Added account_balance field to ValidationResult:**
```python
@dataclass
class ValidationResult:
    approved: bool
    violations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    confidence_threshold: float = 0.0
    risk_threshold: float = 0.0
    position_value: float = 0.0
    risk_amount: float = 0.0
    account_balance: float = 0.0  # NEW
    daily_drawdown_pct: float = 0.0
    open_positions_count: int = 0
    proposed_trade: Dict[str, Any] = field(default_factory=dict)
```

#### 2. Updated Trading Service ([app/execution/trading_service.py](file:///home/admin/.openclaw/workspace/auto-trade-system/app/execution/trading_service.py))

Pass account balance to validator in all execution modes:
```python
validation = await self.validator.validate_trade(
    proposal=proposal,
    user_id=user_id,
    db_session=db_session,
    exchange=self.exchange_name,
    symbol=symbol,
    account_balance=balance.get('total_usdt') if balance else None  # NEW
)
```

Applied to:
- `proposal` mode
- `semi-auto` mode
- `fully-auto` mode
- Live MEXC trades

#### 3. Updated Dashboard API ([app/dashboard/trading_api.py](file:///home/admin/.openclaw/workspace/auto-trade-system/app/dashboard/trading_api.py))

Fetch balance before validation:
```python
# Fetch account balance for risk validation
try:
    balance = await service.exchange_manager.fetch_balance()
    account_balance = balance.get('total_usdt') if balance else None
except Exception as e:
    logger.warning(f"Could not fetch balance for validation: {e}")
    account_balance = None

validation = await validator.validate_trade(
    proposal=proposal,
    user_id=user_id,
    db_session=db_session,
    exchange="mexc",
    symbol=settings.GOLD_SYMBOL_MEXC,
    account_balance=account_balance  # NEW
)
```

#### 4. Updated Test Scripts

Updated all test scripts to pass account balance:
- [scripts/test_trade_validation.py](file:///home/admin/.openclaw/workspace/auto-trade-system/scripts/test_trade_validation.py)
- [scripts/validate_complete_trade_cycle.py](file:///home/admin/.openclaw/workspace/auto-trade-system/scripts/validate_complete_trade_cycle.py)

## Benefits

### 1. Consistency
Position sizing and validation now use the same risk model (account-based), eliminating false rejections.

### 2. Professional Standard
Account-based risk management is the industry standard used by professional trading systems.

### 3. Better Capital Efficiency
Properly-sized trades are no longer rejected, improving trading opportunities.

### 4. Backward Compatibility
If account balance is not provided, the validator falls back to position-based validation with a warning.

### 5. Clear Error Messages
Validation errors now clearly indicate whether risk is calculated against account balance or position value.

## Testing

Created comprehensive test script: [scripts/test_account_based_risk_validation.py](file:///home/admin/.openclaw/workspace/auto-trade-system/scripts/test_account_based_risk_validation.py)

**Test Results:**
```
✅ FIX VERIFIED!

The validator now correctly:
  1. Uses account-based risk model when balance is provided
  2. Falls back to position-based model when balance is missing
  3. Aligns with position sizing logic (which uses account balance)

This resolves the issue where small positions were incorrectly rejected
due to mismatched risk calculation models.

✅ CONSISTENCY VERIFIED!
Position sizing and validation both use account-based risk model.
```

## Migration Notes

### For Existing Code

All calls to `validator.validate_trade()` should be updated to include `account_balance`:

**Before:**
```python
result = await validator.validate_trade(
    proposal=proposal,
    user_id=user_id,
    db_session=db_session,
    exchange='mexc',
    symbol='XAU/USDT'
)
```

**After:**
```python
balance = await exchange_manager.fetch_balance()
result = await validator.validate_trade(
    proposal=proposal,
    user_id=user_id,
    db_session=db_session,
    exchange='mexc',
    symbol='XAU/USDT',
    account_balance=balance.get('total_usdt') if balance else None
)
```

### For New Integrations

Always provide account balance when calling the validator to ensure proper risk validation.

## Files Modified

1. [app/risk/validator.py](file:///home/admin/.openclaw/workspace/auto-trade-system/app/risk/validator.py) - Core validation logic
2. [app/execution/trading_service.py](file:///home/admin/.openclaw/workspace/auto-trade-system/app/execution/trading_service.py) - Pass balance to validator
3. [app/dashboard/trading_api.py](file:///home/admin/.openclaw/workspace/auto-trade-system/app/dashboard/trading_api.py) - Fetch and pass balance
4. [scripts/test_trade_validation.py](file:///home/admin/.openclaw/workspace/auto-trade-system/scripts/test_trade_validation.py) - Updated tests
5. [scripts/validate_complete_trade_cycle.py](file:///home/admin/.openclaw/workspace/auto-trade-system/scripts/validate_complete_trade_cycle.py) - Updated tests
6. [scripts/test_account_based_risk_validation.py](file:///home/admin/.openclaw/workspace/auto-trade-system/scripts/test_account_based_risk_validation.py) - New verification test

## Verification

Run the test to verify the fix:
```bash
python scripts/test_account_based_risk_validation.py
```

Expected output: All tests pass with account-based validation working correctly.

---

**Date:** 2026-05-18  
**Issue:** Trade rejections due to risk validation mismatch  
**Solution:** Switch to account-based risk model  
**Status:** ✅ Implemented and Verified
