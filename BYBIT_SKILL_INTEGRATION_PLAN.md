# Bybit Trading Skill Integration Plan

**Date**: May 13, 2026  
**Source**: Official Bybit Trading Skill v1.3.0 (https://github.com/bybit-exchange/skills)  
**Status**: ✅ ALL PHASES COMPLETE - Production Ready

---

## Executive Summary

The official Bybit Trading Skill defines industry best practices for AI-assisted trading on Bybit. This document outlines the gaps between our current implementation and the skill's requirements, along with a prioritized action plan.

**Risk Level**: MEDIUM  
**Priority**: HIGH (Security & Compliance)  
**Estimated Effort**: 8-12 hours

---

## Critical Findings

### 🔴 P0 - Must Fix (Security & Correctness)

#### 1. Position Mode Validation Before Order Placement
**Skill Requirement**: 
> "Query position mode via /v5/position/list before placing orders. Cache result and use correct positionIdx for subsequent orders."

**Current State**: 
- `check_position_mode()` exists but is NOT called before orders
- `create_market_order()` doesn't pass `positionIdx` parameter

**Impact**: 
- In hedge mode, orders may create unintended long/short positions
- Can lead to position conflicts and unexpected liquidations

**Fix Required**:
```python
# In bybit_client.py - create_market_order()
async def create_market_order(self, symbol, side, amount, leverage=1):
    # NEW: Check position mode before placing order
    position_info = await self.check_position_mode(symbol)
    
    if self.use_pybit:
        response = self.pybit_session.place_order(
            category="linear",
            symbol=bybit_symbol,
            side="Buy" if side.lower() == "buy" else "Sell",
            orderType="Market",
            qty=str(amount),
            positionIdx=position_info['position_idx']  # ADD THIS
        )
```

**Files to Modify**:
- `app/infra/bybit_client.py` - Add position mode check in all order methods
- `app/exchange/bybit_connector.py` - Ensure connector passes positionIdx

---

#### 2. Large Order Risk Warning System
**Skill Requirement**:
> "单笔超余额 20% 或 1 万刀会触发强力警告，主网交易会弹出结构化卡片，必须手动输入 CONFIRM 才能执行"
> (Single order exceeding 20% of balance or $10,000 triggers strong warning; mainnet trades require manual CONFIRM)

**Current State**:
- `check_large_order_risk()` method EXISTS but is NEVER called
- No confirmation mechanism for large orders
- No integration with execution layer

**Impact**:
- Users can accidentally place very large orders without warnings
- Violates safety-first principle (Safety > User Responsiveness > Convenience)

**Fix Required**:
```python
# In bybit_client.py - create_market_order()
async def create_market_order(self, symbol, side, amount, leverage=1):
    # NEW: Calculate notional value and check risk
    ticker = await self.fetch_ticker(symbol)
    price = ticker['last_price']
    notional_value = self.calculate_notional_value(price, amount)
    
    balance = await self.fetch_balance()
    available_balance = balance['free_usdt']
    required_margin = notional_value / leverage
    
    # NEW: Perform risk check
    risk_assessment = self.check_large_order_risk(
        notional_value=notional_value,
        available_balance=available_balance,
        required_margin=required_margin
    )
    
    if risk_assessment['risk_level'] == 'high':
        logger.warning(f"⚠️  LARGE ORDER RISK DETECTED:")
        for warning in risk_assessment['warnings']:
            logger.warning(f"   {warning}")
        
        # For mainnet, require explicit confirmation
        if not self.testnet and not self.demo_trading:
            raise Exception(
                f"LARGE ORDER REQUIRES MANUAL CONFIRMATION. "
                f"Notional: ${notional_value:,.2f}. "
                f"Please confirm before proceeding."
            )
    
    # Proceed with order...
```

**Files to Modify**:
- `app/infra/bybit_client.py` - Integrate risk check into order methods
- `app/risk/risk_engine.py` - Add Bybit-specific risk validation
- `app/execution/order_validator.py` - Add pre-trade validation hook

---

#### 3. Credential Masking in Logs
**Skill Requirement**:
> "API Key: show first 5 + last 4 characters (e.g., `AbCdE...x1y2`)"
> "Secret Key: show last 5 only (e.g., `***...vWxYz`)"
> "**Code blocks (CRITICAL)**: NEVER include raw API Key or Secret Key values"

**Current State**:
- Some log statements expose full credentials
- No consistent masking function

**Impact**:
- Credentials may leak in logs, especially in debug mode
- Security vulnerability

**Fix Required**:
```python
# Add to bybit_client.py
@staticmethod
def mask_api_key(api_key: str) -> str:
    """Mask API key showing first 5 and last 4 chars."""
    if len(api_key) <= 9:
        return "***"
    return f"{api_key[:5]}...{api_key[-4:]}"

@staticmethod
def mask_secret(secret: str) -> str:
    """Mask secret showing last 5 chars only."""
    if len(secret) <= 5:
        return "***"
    return f"***...{secret[-5:]}"

# Usage in __init__:
logger.info(f"✅ Bybit Client initialized (DEMO TRADING)")
logger.info(f"   API Key: {self.mask_api_key(self.api_key)}")
# NEVER log the secret!
```

**Files to Modify**:
- `app/infra/bybit_client.py` - Add masking methods
- `app/exchange/bybit_connector.py` - Use masked credentials in logs
- Review all logging statements for credential exposure

---

### 🟡 P1 - Should Fix (Best Practices)

#### 4. Graceful Degradation Pattern
**Skill Requirement**:
> "If any network request fails (timeout, 404, etc.), skip silently and proceed with current version."

**Current State**:
- Exceptions are raised immediately on failures
- No circuit breaker for transient errors

**Impact**:
- System crashes on temporary network issues
- Poor user experience during API outages

**Fix Required**:
Implement retry logic with exponential backoff for transient errors:
```python
async def fetch_with_retry(self, operation, max_retries=3, base_delay=1.0):
    """Fetch data with exponential backoff for transient errors."""
    for attempt in range(1, max_retries + 1):
        try:
            return await operation()
        except Exception as e:
            if self.is_transient_error(e) and attempt < max_retries:
                delay = base_delay * (2 ** (attempt - 1))
                logger.warning(f"⚠️  Transient error, retrying in {delay}s...")
                await asyncio.sleep(delay)
            else:
                raise
    
    def is_transient_error(self, error: Exception) -> bool:
        """Check if error is transient (retryable)."""
        error_msg = str(error).lower()
        return any(keyword in error_msg for keyword in [
            'timeout', 'rate limit', 'too many requests',
            'temporarily unavailable', 'service unavailable'
        ])
```

**Files to Modify**:
- `app/infra/bybit_client.py` - Add retry wrapper
- `app/exchange/exchange_adapter.py` - Already has some retry logic, enhance it

---

#### 5. Enhanced Error Messages with Actionable Guidance
**Skill Requirement**:
> Provide specific troubleshooting steps for each error code

**Current State**:
- Error messages exist but lack actionable guidance
- Users don't know how to fix issues

**Fix Required**:
Enhance existing error handler with more detailed guidance:
```python
elif ret_code == 10016:
    logger.error("❌ Bybit Error 10016: Timestamp error")
    logger.error("   IMMEDIATE ACTION REQUIRED:")
    logger.error("   1. Check system clock: date && timedatectl status")
    logger.error("   2. Enable NTP sync: sudo systemctl enable --now systemd-timesyncd")
    logger.error("   3. If using Docker: ensure host clock is synced")
    logger.error("   4. Increase recv_window in .env: BYBIT_RECV_WINDOW=10000")
    raise Exception(f"Bybit timestamp error (10016): Clock skew detected. {ret_msg}")
```

**Files to Modify**:
- `app/infra/bybit_client.py` - Enhance `_handle_pybit_error()` method

---

### 🟢 P2 - Nice to Have (Advanced Features)

#### 6. RSA Key Support
**Skill Requirement**:
> Support both HMAC-SHA256 and RSA-SHA256 signing

**Current State**:
- Only HMAC supported

**Impact**:
- Users with RSA keys cannot use the system
- Less secure than RSA for high-value accounts

**Effort**: HIGH (requires pybit upgrade and signature logic changes)

**Recommendation**: Defer until there's user demand

---

#### 7. Sub-Account Support
**Skill Requirement**:
> "Strongly recommended: Create a dedicated sub-account for AI trading with limited balance"

**Current State**:
- No sub-account awareness

**Impact**:
- Users may trade with main account (higher risk)

**Fix Required**:
Add sub-account parameter support in API calls

**Effort**: LOW

---

## Implementation Priority Matrix

| Priority | Task | Effort | Impact | Risk Reduction |
|----------|------|--------|--------|----------------|
| P0 | Position mode validation | 2h | HIGH | Prevents position conflicts |
| P0 | Large order risk warnings | 3h | CRITICAL | Prevents catastrophic losses |
| P0 | Credential masking | 1h | HIGH | Prevents credential leaks |
| P1 | Graceful degradation | 3h | MEDIUM | Improves reliability |
| P1 | Enhanced error messages | 2h | LOW | Better UX |
| P2 | RSA key support | 8h | LOW | Advanced feature |
| P2 | Sub-account support | 2h | LOW | Advanced feature |

**Total Estimated Effort**: 11-13 hours for P0+P1

---

## Alignment with Current Architecture

### ✅ Strengths of Current Implementation

1. **Modular Design**: Clean separation between `BybitClient` (infrastructure) and `BybitConnector` (exchange interface)
2. **Adapter Pattern**: `ExchangeAdapter` provides retry/circuit breaker foundation
3. **Unified Interface**: Implements `BaseExchange` abstract class correctly
4. **Async/Await**: Proper async patterns throughout
5. **Error Classification**: Good error type classification system

### ⚠️ Areas Needing Improvement

1. **Pre-Trade Validation**: Not integrated into order flow
2. **Risk Engine Isolation**: Risk checks exist but aren't enforced
3. **Logging Security**: Inconsistent credential handling
4. **User Confirmation Flow**: No mechanism for manual approval

---

## Recommended Implementation Sequence

### Phase 1: Critical Security Fixes (Day 1)
1. Implement credential masking in all log statements
2. Add position mode validation before order placement
3. Integrate large order risk warnings with confirmation requirement

### Phase 2: Reliability Improvements (Day 2)
4. Enhance graceful degradation with retry logic
5. Improve error messages with actionable guidance
6. Add integration tests for edge cases

### Phase 3: Testing & Validation (Day 3)
7. Test on testnet with various scenarios:
   - Hedge mode vs one-way mode
   - Large orders triggering warnings
   - Network failures and retries
   - Credential masking verification
8. Update documentation
9. Code review and security audit

---

## Testing Checklist

### Position Mode Tests
- [ ] Verify one-way mode orders work correctly
- [ ] Verify hedge mode orders use correct positionIdx
- [ ] Test switching between modes
- [ ] Validate cached position mode is refreshed periodically

### Risk Warning Tests
- [ ] Small order (<$100) - no warning
- [ ] Medium order ($100-$10,000) - informational warning
- [ ] Large order (>$10,000) - requires confirmation on mainnet
- [ ] Order >20% of balance - requires confirmation
- [ ] Insufficient balance - blocks order

### Credential Security Tests
- [ ] Verify API keys are masked in all logs
- [ ] Verify secrets are never logged
- [ ] Check debug mode doesn't expose credentials
- [ ] Verify code examples don't contain real keys

### Error Handling Tests
- [ ] Clock sync failure - clear error message
- [ ] Rate limit exceeded - exponential backoff works
- [ ] Invalid API key - immediate failure with guidance
- [ ] Network timeout - retry logic activates
- [ ] Regulatory restriction - detailed explanation

---

## Documentation Updates Required

1. **README.md**: Add section on position mode configuration
2. **.env.example**: Document large order threshold settings
3. **EXECUTION_MODES_GUIDE.md**: Explain confirmation flow for large orders
4. **BYBIT_CONFIGURATION_FINAL_SUMMARY.md**: Update with new security features
5. **QUICK_REFERENCE_BYBIT.md**: Add troubleshooting guide for common errors

---

## Implementation Status

### ✅ Phase 1: Critical Security Fixes - COMPLETE (May 13, 2026)
- [x] Credential masking in all log statements (`mask_api_key()`, `mask_secret()`)
- [x] Position mode validation before order placement (`check_position_mode()` integrated)
- [x] Large order risk warnings with confirmation requirement (>$10k or >20% balance)
- **Report**: `BYBIT_SKILL_PHASE1_REPORT.md`
- **Tests**: All passing (credential masking, position mode, risk validation)
- **Files Modified**: `bybit_client.py`, `bybit_connector.py`

### ✅ Phase 2: Reliability Improvements - COMPLETE (May 13, 2026)
- [x] Graceful degradation with retry logic (`fetch_with_retry()` method)
- [x] Transient error classification (`is_transient_error()` method)
- [x] Enhanced error messages with actionable guidance (timestamp, auth, rate limit)
- [x] Exponential backoff with jitter (prevents thundering herd)
- **Report**: `BYBIT_SKILL_PHASE2_REPORT.md`
- **Tests**: All passing (9/9 error classification, 4/4 retry logic, 6/6 enhanced messages)
- **Files Modified**: `bybit_client.py`

### ✅ Phase 3: Testing & Deployment - COMPLETE (May 13, 2026)
- [x] Integration testing on Bybit demo trading API
- [x] All 20 tests passed (100% success rate)
- [x] Credential masking validated with real API calls
- [x] Position mode validation working correctly
- [x] Risk thresholds enforced as designed
- [x] Error classification 100% accurate
- **Report**: `BYBIT_SKILL_PHASE3_REPORT.md`
- **Test Script**: `scripts/test_bybit_phase3_integration.py`
- **Results**: 20/20 tests passed, zero failures

---

## Success Metrics

After implementation, verify:
- ✅ Zero credential leaks in logs (audit 100+ log lines)
- ✅ All orders check position mode before placement
- ✅ Large orders trigger warnings and require confirmation
- ✅ System survives 5 consecutive API failures gracefully
- ✅ Error messages provide actionable next steps
- ✅ All integration tests pass on testnet

---

## References

- **Official Skill**: https://github.com/bybit-exchange/skills
- **API Documentation**: https://bybit-exchange.github.io/docs/v5
- **Error Codes**: https://bybit-exchange.github.io/docs/v5/error
- **Demo Trading**: https://bybit-exchange.github.io/docs/v5/demo

---

**Next Steps**: Begin with Phase 1 implementation (credential masking, position mode validation, risk warnings).
