#!/bin/bash
# Validation Cycle - Quick Status Dashboard
# Run this anytime for instant system status

LOG_DIR="/home/admin/.openclaw/workspace/auto-trade-system/logs"
TODAY=$(date +%Y-%m-%d)

echo "╔══════════════════════════════════════════════════════════╗"
echo "║     Auto Trade System - Validation Status Dashboard    ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# Get current time
CURRENT_TIME=$(date '+%Y-%m-%d %H:%M:%S UTC')
echo "📅 Timestamp: $CURRENT_TIME"
echo ""

# 1. Application Health
echo "┌─────────────────────────────────────────────────────────┐"
echo "│ 1️⃣  APPLICATION STATUS                                  │"
echo "└─────────────────────────────────────────────────────────┘"

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

# 2. Execution Mode
echo "┌─────────────────────────────────────────────────────────┐"
echo "│ 2️⃣  EXECUTION MODE                                      │"
echo "└─────────────────────────────────────────────────────────┘"

EXEC_MODE=$(grep "^EXECUTION_MODE=" .env | cut -d'=' -f2)
echo "   Current Mode: $EXEC_MODE"

if [ "$EXEC_MODE" = "paper" ]; then
    echo "   ✅ Safe mode active (paper trading)"
elif [ "$EXEC_MODE" = "fully-auto" ]; then
    echo "   ⚠️  LIVE TRADING MODE - Exercise caution!"
else
    echo "   ℹ️  Mode: $EXEC_MODE"
fi
echo ""

# 3. Position Sync Status
echo "┌─────────────────────────────────────────────────────────┐"
echo "│ 3️⃣  POSITION SYNC STATUS                                │"
echo "└─────────────────────────────────────────────────────────┘"

SYNC_LOG="$LOG_DIR/all_${TODAY}.log"
if [ -f "$SYNC_LOG" ]; then
    # Check recent sync activity
    RECENT_SYNC=$(tail -50 "$SYNC_LOG" | grep "Position sync" | tail -1)
    if [ -n "$RECENT_SYNC" ]; then
        SYNC_TIME=$(echo "$RECENT_SYNC" | grep -oP '^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}')
        SYNC_MSG=$(echo "$RECENT_SYNC" | grep -oP '(?<=position_sync - ).*')
        echo "   ✅ Last sync: [$SYNC_TIME]"
        echo "      $SYNC_MSG"
    else
        echo "   ⚠️  No recent sync activity found"
    fi
    
    # Count sync errors today
    SYNC_ERRORS=$(grep -c "position_sync.*ERROR" "$SYNC_LOG" 2>/dev/null || echo "0")
    echo "   Total sync errors today: $SYNC_ERRORS"
else
    echo "   ⚠️  Log file not found"
fi
echo ""

# 4. Error Summary
echo "┌─────────────────────────────────────────────────────────┐"
echo "│ 4️⃣  ERROR SUMMARY                                       │"
echo "└─────────────────────────────────────────────────────────┘"

ERROR_LOG="$LOG_DIR/error_${TODAY}.log"
if [ -f "$ERROR_LOG" ]; then
    TOTAL_ERRORS=$(wc -l < "$ERROR_LOG")
    echo "   Total errors today: $TOTAL_ERRORS"
    
    if [ "$TOTAL_ERRORS" -gt 0 ]; then
        echo ""
        echo "   Recent errors:"
        tail -3 "$ERROR_LOG" | while read line; do
            echo "      $line"
        done
    else
        echo "   ✅ No errors recorded"
    fi
else
    echo "   ✅ No error log (or no errors)"
fi
echo ""

# 5. Telegram Notification System
echo "┌─────────────────────────────────────────────────────────┐"
echo "│ 5️⃣  TELEGRAM NOTIFICATION SYSTEM                        │"
echo "└─────────────────────────────────────────────────────────┘"

BOT_TOKEN=$(grep "^TELEGRAM_BOT_TOKEN=" .env | cut -d'=' -f2)
CHAT_ID=$(grep "^TELEGRAM_CHAT_ID=" .env | cut -d'=' -f2)

if [ -n "$BOT_TOKEN" ] && [ "$BOT_TOKEN" != "your-telegram-bot-token-here" ]; then
    echo "   ✅ Bot token configured"
else
    echo "   ❌ Bot token not configured"
fi

if [ -n "$CHAT_ID" ]; then
    echo "   ✅ Chat ID configured"
else
    echo "   ❌ Chat ID not configured"
fi

# Check recent Telegram activity
if [ -f "$SYNC_LOG" ]; then
    TELEGRAM_COUNT=$(grep -c "Telegram" "$SYNC_LOG" 2>/dev/null || echo "0")
    echo "   Telegram events today: $TELEGRAM_COUNT"
fi
echo ""

# 6. Validation Progress
echo "┌─────────────────────────────────────────────────────────┐"
echo "│ 6️⃣  VALIDATION PROGRESS                                 │"
echo "└─────────────────────────────────────────────────────────┘"

VALIDATION_LOG="$LOG_DIR/validation_cycle.log"
if [ -f "$VALIDATION_LOG" ]; then
    START_LINE=$(head -1 "$VALIDATION_LOG")
    echo "   $START_LINE"
    
    # Calculate elapsed time
    if [ -f "/tmp/validation_start_time" ]; then
        START_TIME=$(cat /tmp/validation_start_time)
        CURRENT_TS=$(date +%s)
        ELAPSED=$((CURRENT_TS - START_TIME))
        HOURS=$((ELAPSED / 3600))
        MINUTES=$(((ELAPSED % 3600) / 60))
        echo "   Elapsed: ${HOURS}h ${MINUTES}m"
        echo "   Target: 24-48 hours minimum"
        
        if [ "$HOURS" -lt 24 ]; then
            REMAINING=$((24 - HOURS))
            echo "   ⏳ Remaining: ~${REMAINING} hours to minimum target"
        else
            echo "   ✅ Minimum 24-hour target reached!"
        fi
    fi
else
    echo "   ℹ️  Validation cycle not started yet"
    echo "   Run: ./scripts/monitor_paper_validation.sh"
fi
echo ""

# 7. Critical Checks
echo "┌─────────────────────────────────────────────────────────┐"
echo "│ 7️⃣  CRITICAL CHECKS                                     │"
echo "└─────────────────────────────────────────────────────────┘"

CRITICAL_ISSUES=0

# Check for async generator errors
ASYNC_ERRORS=$(grep -c "async_generator.*does not support" "$SYNC_LOG" 2>/dev/null || echo "0")
if [ "$ASYNC_ERRORS" -eq 0 ]; then
    echo "   ✅ No async generator errors"
else
    echo "   ❌ Found $ASYNC_ERRORS async generator error(s)"
    CRITICAL_ISSUES=$((CRITICAL_ISSUES + 1))
fi

# Check for position sync AttributeError
ATTR_ERRORS=$(grep -c "AttributeError.*fetch_positions\|AttributeError.*get_open_positions" "$SYNC_LOG" 2>/dev/null || echo "0")
if [ "$ATTR_ERRORS" -eq 0 ]; then
    echo "   ✅ No position sync AttributeError"
else
    echo "   ❌ Found $ATTR_ERRORS AttributeError(s)"
    CRITICAL_ISSUES=$((CRITICAL_ISSUES + 1))
fi

# Check for reconciliation mismatches
RECON_ERRORS=$(grep -c "reconciliation.*mismatch\|SYNC_MISMATCH" "$SYNC_LOG" 2>/dev/null || echo "0")
if [ "$RECON_ERRORS" -eq 0 ]; then
    echo "   ✅ No reconciliation mismatches"
else
    echo "   ⚠️  Found $RECON_ERRORS reconciliation event(s)"
fi

echo ""
if [ "$CRITICAL_ISSUES" -eq 0 ]; then
    echo "   🎉 ALL CRITICAL CHECKS PASSED"
else
    echo "   🚨 $CRITICAL_ISSUES CRITICAL ISSUE(S) DETECTED"
fi
echo ""

echo "═══════════════════════════════════════════════════════════"
echo "Quick Commands:"
echo "  • Full status: ./scripts/check_validation_status.sh"
echo "  • Telegram health: ./scripts/check_telegram_health.sh"
echo "  • View logs: tail -f logs/all_${TODAY}.log"
echo "  • View errors: tail -f logs/error_${TODAY}.log"
echo "═══════════════════════════════════════════════════════════"
