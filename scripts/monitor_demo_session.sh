#!/bin/bash
# Quick Monitoring Script for Demo Trading Session
# Usage: ./monitor_demo_session.sh

LOG_FILE="demo_trading_session.log"

echo "================================================================================"
echo "  DEMO TRADING SESSION - QUICK MONITOR"
echo "================================================================================"
echo ""

# Check if session is running
if ps aux | grep run_demo_profit_session | grep -v grep > /dev/null; then
    echo "✅ Session Status: RUNNING"
    PID=$(ps aux | grep run_demo_profit_session | grep -v grep | awk '{print $2}')
    echo "   Process ID: $PID"
else
    echo "❌ Session Status: NOT RUNNING"
    echo "   Start with: nohup python3 scripts/run_demo_profit_session.py > demo_trading_session.log 2>&1 &"
    exit 1
fi

echo ""

# Check log file exists
if [ ! -f "$LOG_FILE" ]; then
    echo "❌ Log file not found: $LOG_FILE"
    exit 1
fi

echo "📊 Session Statistics:"
echo "--------------------------------------------------------------------------------"

# Count cycles
TOTAL_CYCLES=$(grep "CYCLE #" "$LOG_FILE" | wc -l)
echo "   Total Cycles: $TOTAL_CYCLES"

# Count successful trades
SUCCESSFUL=$(grep "Cycle Status: SUCCESS" "$LOG_FILE" | wc -l)
echo "   Successful Trades: $SUCCESSFUL"

# Count rejected trades
REJECTED=$(grep "REJECTED" "$LOG_FILE" | wc -l)
echo "   Rejected (Quality Filter): $REJECTED"

# Count failed trades
FAILED=$(grep "Cycle Status: FAILED" "$LOG_FILE" | wc -l)
echo "   Failed: $FAILED"

echo ""
echo "💰 Profit Tracking:"
echo "--------------------------------------------------------------------------------"

# Get latest profit update
LATEST_PROFIT=$(grep "Total Current Profit:" "$LOG_FILE" | tail -1 | awk '{print $5}')
LATEST_TARGET=$(grep "Target:" "$LOG_FILE" | tail -1 | awk '{print $3}')
LATEST_PROGRESS=$(grep "Progress:" "$LOG_FILE" | tail -1 | awk '{print $3}')

echo "   Current Profit: $LATEST_PROFIT"
echo "   Target: $LATEST_TARGET"
echo "   Progress: $LATEST_PROGRESS"

echo ""
echo "🔍 Recent Activity (Last 3 Cycles):"
echo "--------------------------------------------------------------------------------"

# Show last 3 cycle summaries
grep -A 8 "CYCLE #" "$LOG_FILE" | tail -24

echo ""
echo "⚠️  Quality Filter Stats:"
echo "--------------------------------------------------------------------------------"

# Show quality score distribution
if grep "Quality Score:" "$LOG_FILE" > /dev/null; then
    echo "   Quality Score Distribution:"
    grep "Quality Score:" "$LOG_FILE" | awk '{print $4}' | sort | uniq -c | sort -rn
else
    echo "   No quality scores recorded yet"
fi

echo ""
echo "🛡️  Safety Verification:"
echo "--------------------------------------------------------------------------------"

# Verify demo mode
if grep "BINANCE_TESTNET: True" "$LOG_FILE" > /dev/null || grep "FUTURES DEMO MODE" "$LOG_FILE" > /dev/null; then
    echo "   ✅ Demo Mode: ACTIVE"
    echo "   ✅ API Endpoint: demo-fapi.binance.com"
    echo "   ✅ Financial Risk: NONE (virtual funds only)"
else
    echo "   ❌ WARNING: Could not verify demo mode!"
fi

echo ""
echo "================================================================================"
echo "  MONITORING COMMANDS"
echo "================================================================================"
echo ""
echo "   Follow live logs:     tail -f $LOG_FILE"
echo "   Check progress:       grep 'Progress:' $LOG_FILE | tail -5"
echo "   View errors:          grep -i error $LOG_FILE | tail -10"
echo "   Stop session:         kill $PID"
echo ""
echo "================================================================================"
