#!/bin/bash
# =============================================================================
# Quick Start Script - Continue Paper Trading Validation
# =============================================================================
# This script helps you immediately continue the paper trading validation
# from the current state (5 trades completed, need 15 more).
#
# Usage: bash scripts/continue_validation.sh
# =============================================================================

set -e  # Exit on error

echo "========================================================================"
echo "🚀 Auto Trade System - Continue Paper Trading Validation"
echo "========================================================================"
echo ""
echo "Current State: 5/20 trades completed"
echo "Goal: Execute 15 more trades to reach 20-trade minimum"
echo ""

# Check if we're in the right directory
if [ ! -f "data/vmassit.db" ]; then
    echo "❌ Error: Not in project root directory"
    echo "   Please run: cd /home/admin/.openclaw/workspace/auto-trade-system"
    exit 1
fi

# Activate virtual environment
echo "✅ Activating virtual environment..."
source .venv/bin/activate

# Check current trade count
echo ""
echo "📊 Checking current trade count..."
TRADE_COUNT=$(python3 -c "import sqlite3; conn=sqlite3.connect('data/vmassit.db'); c=conn.cursor(); c.execute('SELECT COUNT(*) FROM paper_trades WHERE status=\"closed\"'); print(c.fetchone()[0]); conn.close()")
echo "   Current closed trades: $TRADE_COUNT/20"

if [ "$TRADE_COUNT" -ge 20 ]; then
    echo ""
    echo "✅ Already have 20+ trades! Ready for validation phase."
    echo "   Run: python scripts/validate_production_readiness.py"
    exit 0
fi

TRADES_NEEDED=$((20 - TRADE_COUNT))
echo "   Trades needed: $TRADES_NEEDED"
echo ""

# Ask user how many trades to execute
echo "How many trades would you like to execute now?"
echo "  1) Execute 5 trades (recommended for today)"
echo "  2) Execute 10 trades"
echo "  3) Execute all remaining $TRADES_NEEDED trades"
echo "  4) Custom number"
read -p "Enter choice (1-4): " CHOICE

case $CHOICE in
    1)
        NUM_TRADES=5
        ;;
    2)
        NUM_TRADES=10
        ;;
    3)
        NUM_TRADES=$TRADES_NEEDED
        ;;
    4)
        read -p "Enter number of trades: " NUM_TRADES
        ;;
    *)
        echo "❌ Invalid choice"
        exit 1
        ;;
esac

# Validate number
if [ "$NUM_TRADES" -gt "$TRADES_NEEDED" ]; then
    echo "⚠️  Warning: Requested $NUM_TRADES trades but only $TRADES_NEEDED needed"
    read -p "Continue with $TRADES_NEEDED trades? (y/n): " CONFIRM
    if [ "$CONFIRM" != "y" ]; then
        echo "Aborted."
        exit 0
    fi
    NUM_TRADES=$TRADES_NEEDED
fi

echo ""
echo "========================================================================"
echo "📋 Execution Plan"
echo "========================================================================"
echo "   Trades to execute: $NUM_TRADES"
echo "   Starting from trade #: $((TRADE_COUNT + 1))"
echo "   Delay between trades: 5 minutes (300 seconds)"
echo "   Estimated time: $((NUM_TRADES * 5)) minutes"
echo ""
read -p "Ready to start? (y/n): " START_CONFIRM

if [ "$START_CONFIRM" != "y" ]; then
    echo "Aborted. Run this script when ready."
    exit 0
fi

# Check if system is running
echo ""
echo "🔍 Checking if system is running..."
if ps aux | grep -q "[u]vicorn app.main"; then
    echo "   ✅ System is running"
else
    echo "   ⚠️  System is not running"
    read -p "Start system now? (y/n): " START_SYSTEM
    if [ "$START_SYSTEM" = "y" ]; then
        echo "   Starting system..."
        python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &
        sleep 5
        echo "   ✅ System started"
    else
        echo "❌ System must be running to execute trades"
        exit 1
    fi
fi

# Execute trades
echo ""
echo "========================================================================"
echo "🔄 Executing Trades"
echo "========================================================================"

SUCCESS_COUNT=0
FAIL_COUNT=0

for i in $(seq 1 $NUM_TRADES); do
    TRADE_NUM=$((TRADE_COUNT + i))
    echo ""
    echo "--- Trade #$TRADE_NUM ($i/$NUM_TRADES) ---"
    
    if python scripts/execute_gold_trade.py; then
        echo "   ✅ Trade #$TRADE_NUM executed successfully"
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
    else
        echo "   ❌ Trade #$TRADE_NUM failed"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
    
    # Wait before next trade (except after last one)
    if [ $i -lt $NUM_TRADES ]; then
        echo "   ⏱️  Waiting 5 minutes before next trade..."
        sleep 300
    fi
done

# Summary
echo ""
echo "========================================================================"
echo "📊 Execution Summary"
echo "========================================================================"
echo "   Trades attempted: $NUM_TRADES"
echo "   Successful: $SUCCESS_COUNT"
echo "   Failed: $FAIL_COUNT"
echo ""

# Check new total
NEW_TOTAL=$(python3 -c "import sqlite3; conn=sqlite3.connect('data/vmassit.db'); c=conn.cursor(); c.execute('SELECT COUNT(*) FROM paper_trades WHERE status=\"closed\"'); print(c.fetchone()[0]); conn.close()")
echo "   New total closed trades: $NEW_TOTAL/20"
echo ""

if [ "$NEW_TOTAL" -ge 20 ]; then
    echo "✅ Congratulations! You've reached the 20-trade minimum!"
    echo ""
    echo "Next steps:"
    echo "  1. Run validation: python scripts/validate_production_readiness.py"
    echo "  2. Analyze performance: See PRODUCTION_DEPLOYMENT_PLAN_v2026.md"
    echo "  3. If validation passes, proceed to pre-launch preparation"
else
    REMAINING=$((20 - NEW_TOTAL))
    echo "⏸️  Still need $REMAINING more trades to reach minimum."
    echo ""
    echo "Next steps:"
    echo "  1. Run this script again to execute more trades"
    echo "  2. Or execute manually: python scripts/execute_gold_trade.py"
    echo "  3. Monitor progress: watch -n 60 'python3 -c \"import sqlite3; conn=sqlite3.connect(\\\"data/vmassit.db\\\"); c=conn.cursor(); c.execute(\\\"SELECT COUNT(*) FROM paper_trades WHERE status=\\\\\\\"closed\\\\\\\"\\\"); print(f\\\"Closed trades: {c.fetchone()[0]}/20\\\"); conn.close()\"'"
fi

echo ""
echo "========================================================================"
echo "📚 Documentation Reference"
echo "========================================================================"
echo "   Full plan: PRODUCTION_DEPLOYMENT_PLAN_v2026.md"
echo "   Status: PRODUCTION_DEPLOYMENT_STATUS_v2026.md"
echo "   Quick ref: PRODUCTION_DEPLOYMENT_QUICKREF_v2026.md"
echo "   Overview: PRODUCTION_DEPLOYMENT_README_v2026.md"
echo "========================================================================"
echo ""
echo "✅ Done!"
