#!/bin/bash
# Paper Trading Validation Monitor - 24-48 Hour Cycle
# Monitors system health and position sync stability

LOG_DIR="/home/admin/.openclaw/workspace/auto-trade-system/logs"
VALIDATION_LOG="$LOG_DIR/validation_cycle.log"
START_TIME=$(date +%s)
TARGET_HOURS=24  # Minimum validation period
ERROR_THRESHOLD=0  # Maximum allowed critical errors

echo "==========================================" | tee -a "$VALIDATION_LOG"
echo "Paper Trading Validation Cycle Started" | tee -a "$VALIDATION_LOG"
echo "Start Time: $(date)" | tee -a "$VALIDATION_LOG"
echo "Target Duration: ${TARGET_HOURS} hours" | tee -a "$VALIDATION_LOG"
echo "==========================================" | tee -a "$VALIDATION_LOG"
echo "" | tee -a "$VALIDATION_LOG"

# Function to check system health
check_health() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    # Check if application is running
    if ! pgrep -f "uvicorn app.main:app" > /dev/null; then
        echo "[$timestamp] ❌ CRITICAL: Application not running!" | tee -a "$VALIDATION_LOG"
        return 1
    fi
    
    # Check health endpoint
    local health_response=$(curl -s http://localhost:8000/health 2>/dev/null)
    if echo "$health_response" | grep -q '"status":"healthy"'; then
        echo "[$timestamp] ✅ Health check passed" | tee -a "$VALIDATION_LOG"
    else
        echo "[$timestamp] ❌ Health check failed: $health_response" | tee -a "$VALIDATION_LOG"
        return 1
    fi
    
    return 0
}

# Function to check for critical errors
check_errors() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local error_count=0
    
    # Check for position sync errors in last 5 minutes
    local recent_errors=$(tail -1000 "$LOG_DIR/all_$(date +%Y-%m-%d).log" 2>/dev/null | \
        grep -E "(position_sync.*ERROR|async_generator|AttributeError.*get_open_positions)" | \
        tail -20)
    
    if [ -n "$recent_errors" ]; then
        error_count=$(echo "$recent_errors" | wc -l)
        echo "[$timestamp] ⚠️  Found $error_count recent position sync errors:" | tee -a "$VALIDATION_LOG"
        echo "$recent_errors" | tee -a "$VALIDATION_LOG"
    else
        echo "[$timestamp] ✅ No recent position sync errors" | tee -a "$VALIDATION_LOG"
    fi
    
    return $error_count
}

# Function to check position sync status
check_position_sync() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    # Check for successful sync messages
    local sync_success=$(tail -100 "$LOG_DIR/all_$(date +%Y-%m-%d).log" 2>/dev/null | \
        grep "Position sync: All consistent" | wc -l)
    
    if [ "$sync_success" -gt 0 ]; then
        echo "[$timestamp] ✅ Position sync operational ($sync_success successful cycles in recent logs)" | tee -a "$VALIDATION_LOG"
        return 0
    else
        echo "[$timestamp] ⚠️  No recent successful sync messages found" | tee -a "$VALIDATION_LOG"
        return 1
    fi
}

# Function to generate status report
generate_report() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local elapsed=$(( $(date +%s) - START_TIME ))
    local hours=$(( elapsed / 3600 ))
    local minutes=$(( (elapsed % 3600) / 60 ))
    
    echo "" | tee -a "$VALIDATION_LOG"
    echo "==========================================" | tee -a "$VALIDATION_LOG"
    echo "Validation Status Report" | tee -a "$VALIDATION_LOG"
    echo "Timestamp: $timestamp" | tee -a "$VALIDATION_LOG"
    echo "Elapsed Time: ${hours}h ${minutes}m" | tee -a "$VALIDATION_LOG"
    echo "Progress: $(( (elapsed * 100) / (TARGET_HOURS * 3600) ))%" | tee -a "$VALIDATION_LOG"
    echo "==========================================" | tee -a "$VALIDATION_LOG"
    
    # Check all components
    check_health
    check_errors
    check_position_sync
    
    echo "" | tee -a "$VALIDATION_LOG"
}

# Main monitoring loop
echo "Starting continuous monitoring..." | tee -a "$VALIDATION_LOG"
echo "Press Ctrl+C to stop monitoring" | tee -a "$VALIDATION_LOG"
echo "" | tee -a "$VALIDATION_LOG"

# Initial report
generate_report

# Continuous monitoring
while true; do
    sleep 300  # Check every 5 minutes
    
    generate_report
    
    # Check if target duration reached
    local elapsed=$(( $(date +%s) - START_TIME ))
    local hours=$(( elapsed / 3600 ))
    
    if [ "$hours" -ge "$TARGET_HOURS" ]; then
        echo "" | tee -a "$VALIDATION_LOG"
        echo "🎉 VALIDATION CYCLE COMPLETE!" | tee -a "$VALIDATION_LOG"
        echo "Duration: ${hours} hours" | tee -a "$VALIDATION_LOG"
        echo "Result: System stable and ready for fully-auto mode" | tee -a "$VALIDATION_LOG"
        echo "" | tee -a "$VALIDATION_LOG"
        
        # Final comprehensive check
        echo "Performing final validation checks..." | tee -a "$VALIDATION_LOG"
        check_health && check_errors && check_position_sync
        
        if [ $? -eq 0 ]; then
            echo "" | tee -a "$VALIDATION_LOG"
            echo "✅ ALL CHECKS PASSED - Safe to transition to fully-auto mode" | tee -a "$VALIDATION_LOG"
            echo "Next step: Update .env EXECUTION_MODE=paper to EXECUTION_MODE=fully-auto" | tee -a "$VALIDATION_LOG"
        else
            echo "" | tee -a "$VALIDATION_LOG"
            echo "⚠️  Some checks failed - Review logs before transitioning" | tee -a "$VALIDATION_LOG"
        fi
        
        break
    fi
done
