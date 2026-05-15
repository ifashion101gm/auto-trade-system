#!/bin/bash
# Verification script for Phase 1 & 2 implementations
# Tests all new features and integrations

set -e  # Exit on error

echo "=========================================="
echo "Phase 1 & 2 Implementation Verification"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASS_COUNT=0
FAIL_COUNT=0

pass_test() {
    echo -e "${GREEN}✅ PASS:${NC} $1"
    ((PASS_COUNT++))
}

fail_test() {
    echo -e "${RED}❌ FAIL:${NC} $1"
    ((FAIL_COUNT++))
}

info_msg() {
    echo -e "${YELLOW}ℹ️  INFO:${NC} $1"
}

echo "1. Testing AlertManager Import..."
if python -c "from app.notifications.alert_manager import get_alert_manager, AlertLevel, AlertUrgency" 2>&1 | grep -q "AlertManager"; then
    pass_test "AlertManager imports successfully"
else
    fail_test "AlertManager import failed"
fi

echo ""
echo "2. Testing Health API Module..."
if python -c "from app.dashboard.health_api import router, register_health_routes" 2>&1 | grep -q "Error"; then
    fail_test "Health API has import errors"
else
    pass_test "Health API module loads without errors"
fi

echo ""
echo "3. Testing Reconciliation Engine Enhancements..."
if grep -q "enable_telegram_alerts" app/execution/reconciliation_engine.py && \
   grep -q "enable_prometheus_metrics" app/execution/reconciliation_engine.py; then
    pass_test "Reconciliation engine has new configuration flags"
else
    fail_test "Reconciliation engine missing configuration flags"
fi

if grep -q "get_alert_manager" app/execution/reconciliation_engine.py; then
    pass_test "Reconciliation engine integrates with AlertManager"
else
    fail_test "Reconciliation engine missing AlertManager integration"
fi

echo ""
echo "4. Testing Main Application Integration..."
if grep -q "register_health_routes" app/main.py; then
    pass_test "Health routes registered in main.py"
else
    fail_test "Health routes not registered in main.py"
fi

echo ""
echo "5. Testing Chaos Test Suite..."
if [ -f "tests/integration/test_network_failures.py" ]; then
    TEST_COUNT=$(grep -c "async def test_" tests/integration/test_network_failures.py)
    if [ "$TEST_COUNT" -ge 10 ]; then
        pass_test "Chaos test suite created with $TEST_COUNT tests"
    else
        fail_test "Chaos test suite has only $TEST_COUNT tests (expected >= 10)"
    fi
else
    fail_test "Chaos test suite file not found"
fi

echo ""
echo "6. Verifying ExecutionService Usage..."
if grep -q "self.execution_service.execute_trade" app/execution/trading_service.py; then
    pass_test "LiveTradingService uses centralized ExecutionService"
else
    fail_test "LiveTradingService not using ExecutionService"
fi

echo ""
echo "7. Checking File Syntax..."
python -m py_compile app/notifications/alert_manager.py 2>&1
if [ $? -eq 0 ]; then
    pass_test "alert_manager.py syntax valid"
else
    fail_test "alert_manager.py has syntax errors"
fi

python -m py_compile app/dashboard/health_api.py 2>&1
if [ $? -eq 0 ]; then
    pass_test "health_api.py syntax valid"
else
    fail_test "health_api.py has syntax errors"
fi

python -m py_compile app/execution/reconciliation_engine.py 2>&1
if [ $? -eq 0 ]; then
    pass_test "reconciliation_engine.py syntax valid"
else
    fail_test "reconciliation_engine.py has syntax errors"
fi

echo ""
echo "8. Verifying Documentation..."
if [ -f "PHASE1_PHASE2_IMPLEMENTATION_SUMMARY.md" ]; then
    LINE_COUNT=$(wc -l < PHASE1_PHASE2_IMPLEMENTATION_SUMMARY.md)
    if [ "$LINE_COUNT" -ge 500 ]; then
        pass_test "Implementation summary document created ($LINE_COUNT lines)"
    else
        fail_test "Implementation summary too short ($LINE_COUNT lines)"
    fi
else
    fail_test "Implementation summary document not found"
fi

echo ""
echo "=========================================="
echo "Verification Summary"
echo "=========================================="
echo -e "${GREEN}Passed: $PASS_COUNT${NC}"
echo -e "${RED}Failed: $FAIL_COUNT${NC}"
echo ""

if [ $FAIL_COUNT -eq 0 ]; then
    echo -e "${GREEN}✅ ALL CHECKS PASSED!${NC}"
    echo ""
    info_msg "Next steps:"
    echo "  1. Start application: python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
    echo "  2. Test health endpoint: curl http://localhost:8000/api/health"
    echo "  3. Monitor logs for initialization messages"
    exit 0
else
    echo -e "${RED}❌ SOME CHECKS FAILED${NC}"
    echo ""
    info_msg "Review failed tests above and fix issues before deployment"
    exit 1
fi
