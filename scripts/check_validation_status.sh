#!/bin/bash
# Quick Validation Status Check
# Run this anytime to check current validation progress

LOG_DIR="/home/admin/.openclaw/workspace/auto-trade-system/logs"

echo "=========================================="
echo "Auto Trade System - Validation Status"
echo "=========================================="
echo ""

# 1. Check if application is running
echo "1️⃣  Application Status:"
if pgrep -f "uvicorn app.main:app" > /dev/null; then
    PID=$(pgrep -f "uvicorn app.main:app")
    UPTIME=$(ps -p $PID -o etime= 2>/dev/null | xargs)
    echo "   ✅ Running (PID: $PID, Uptime: $UPTIME)"
    
    # Check health endpoint
    HEALTH=$(curl -s http://localhost:8000/health 2>/dev/null)
    if echo "$HEALTH" | grep -q '"status":"healthy"'; then
        echo "   ✅ Health endpoint: HEALTHY"
    else
        echo "   ❌ Health endpoint: UNHEALTHY"
    fi
else
    echo "   ❌ NOT RUNNING"
fi
echo ""

# 2. Check execution mode
echo "2️⃣  Execution Mode:"
EXEC_MODE=$(grep "^EXECUTION_MODE=" /home/admin/.openclaw/workspace/auto-trade-system/.env | cut -d'=' -f2)
echo "   Current mode: $EXEC_MODE"
if [ "$EXEC_MODE" = "paper" ]; then
    echo "   ✅ Safe paper trading mode active"
elif [ "$EXEC_MODE" = "fully-auto" ]; then
    echo "   ⚠️  Fully-auto mode - Ensure validation complete!"
fi
echo ""

# 3. Check position sync status
echo "3️⃣  Position Sync Status:"
TODAY=$(date +%Y-%m-%d)
RECENT_SYNC=$(tail -50 "$LOG_DIR/all_${TODAY}.log" 2>/dev/null | grep "Position sync: All consistent" | wc -l)
RECENT_ERRORS=$(tail -100 "$LOG_DIR/all_${TODAY}.log" 2>/dev/null | grep -E "(position_sync.*ERROR|async_generator|AttributeError)" | wc -l)

if [ "$RECENT_SYNC" -gt 0 ]; then
    echo "   ✅ Position sync operational ($RECENT_SYNC successful cycles in recent logs)"
else
    echo "   ⚠️  No recent successful sync messages"
fi

if [ "$RECENT_ERRORS" -eq 0 ]; then
    echo "   ✅ No recent position sync errors"
else
    echo "   ❌ Found $RECENT_ERRORS recent errors:"
    tail -100 "$LOG_DIR/all_${TODAY}.log" 2>/dev/null | grep -E "(position_sync.*ERROR|async_generator|AttributeError)" | tail -5 | sed 's/^/      /'
fi
echo ""

# 4. Check Bybit connection
echo "4️⃣  Bybit Connection:"
BYBIT_WS=$(tail -50 "$LOG_DIR/all_${TODAY}.log" 2>/dev/null | grep "Bybit DEMO connected with WebSocket" | wc -l)
if [ "$BYBIT_WS" -gt 0 ]; then
    echo "   ✅ Bybit Demo WebSocket connected"
else
    echo "   ⚠️  WebSocket connection status unclear"
fi
echo ""

# 5. Recent error summary
echo "5️⃣  Error Summary (Last 100 lines):"
CRITICAL_ERRORS=$(tail -100 "$LOG_DIR/error_${TODAY}.log" 2>/dev/null | grep -v "get_open_positions\|async_generator" | wc -l)
if [ "$CRITICAL_ERRORS" -eq 0 ]; then
    echo "   ✅ No critical errors (excluding pre-fix historical errors)"
else
    echo "   ⚠️  Found $CRITICAL_ERRORS other errors:"
    tail -100 "$LOG_DIR/error_${TODAY}.log" 2>/dev/null | grep -v "get_open_positions\|async_generator" | tail -3 | sed 's/^/      /'
fi
echo ""

# 6. Validation recommendation
echo "=========================================="
echo "Validation Recommendation:"
echo "=========================================="

# Calculate uptime in minutes
if pgrep -f "uvicorn app.main:app" > /dev/null; then
    START_TIME=$(ps -p $(pgrep -f "uvicorn app.main:app") -o lstart= 2>/dev/null)
    if [ -n "$START_TIME" ]; then
        START_EPOCH=$(date -d "$START_TIME" +%s 2>/dev/null || echo "0")
        CURRENT_EPOCH=$(date +%s)
        if [ "$START_EPOCH" -gt 0 ]; then
            UPTIME_MINUTES=$(( (CURRENT_EPOCH - START_EPOCH) / 60 ))
            echo "Current uptime: ${UPTIME_MINUTES} minutes"
            
            if [ "$UPTIME_MINUTES" -lt 60 ]; then
                echo "⏳ Continue monitoring - Need at least 24 hours"
                echo "   Progress: $(( (UPTIME_MINUTES * 100) / 1440 ))% of 24-hour target"
            elif [ "$UPTIME_MINUTES" -ge 1440 ] && [ "$RECENT_ERRORS" -eq 0 ]; then
                echo "✅ VALIDATION COMPLETE - Ready for fully-auto transition!"
                echo "   Next: Update .env EXECUTION_MODE=fully-auto and restart"
            elif [ "$UPTIME_MINUTES" -ge 1440 ] && [ "$RECENT_ERRORS" -gt 0 ]; then
                echo "⚠️  Uptime sufficient but errors detected - Review before transitioning"
            fi
        fi
    fi
else
    echo "❌ Application not running - Cannot validate"
fi
echo ""
echo "=========================================="
