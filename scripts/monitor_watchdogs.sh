#!/bin/bash
# ============================================================================
# Watchdog Health Monitor - 48-Hour Continuous Monitoring Script
# ============================================================================
# Monitors watchdog health, resource usage, and alert quality
# Usage: ./scripts/monitor_watchdogs.sh [duration_hours]
# ============================================================================

set -euo pipefail

# Configuration
LOG_DIR="logs"
MONITOR_DURATION_HOURS=${1:-48}
CHECK_INTERVAL_SECONDS=${2:-1800}  # Default: 30 minutes
OUTPUT_FILE="logs/watchdog_monitor_$(date +%Y%m%d_%H%M%S).log"

# Color codes for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║         WATCHDOG HEALTH MONITOR - 48 HOUR RUN              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Duration: ${MONITOR_DURATION_HOURS} hours"
echo "Check interval: $((CHECK_INTERVAL_SECONDS / 60)) minutes"
echo "Output file: ${OUTPUT_FILE}"
echo ""
echo "Press Ctrl+C to stop early"
echo ""

# Initialize counters
TOTAL_CHECKS=0
CRITICAL_ALERTS=0
WARNING_ALERTS=0
MEMORY_PEAK_MB=0
CPU_AVG=0.0

# Function to get current memory usage
get_memory_mb() {
    ps aux | grep "[p]ython.*main.py" | awk '{sum += $6} END {printf "%.0f", sum/1024}'
}

# Function to get CPU usage
get_cpu_usage() {
    ps aux | grep "[p]ython.*main.py" | awk '{sum += $3} END {printf "%.1f", sum}'
}

# Function to count log entries
count_log_entries() {
    local pattern=$1
    grep -c "$pattern" ${LOG_DIR}/all_*.log 2>/dev/null || echo 0
}

# Function to get last watchdog status
get_last_watchdog_status() {
    grep "Overall Status" ${LOG_DIR}/all_*.log 2>/dev/null | tail -1 | awk -F': ' '{print $2}' || echo "unknown"
}

# Main monitoring loop
START_TIME=$(date +%s)
END_TIME=$((START_TIME + MONITOR_DURATION_HOURS * 3600))

while [ $(date +%s) -lt $END_TIME ]; do
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
    ELAPSED_MINUTES=$(( ($(date +%s) - START_TIME) / 60 ))
    
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    
    # Collect metrics
    CURRENT_MEMORY=$(get_memory_mb)
    CURRENT_CPU=$(get_cpu_usage)
    CRITICAL_COUNT=$(count_log_entries "CRITICAL\|🚨")
    WARNING_COUNT=$(count_log_entries "WARNING\|⚠️")
    WATCHDOG_STATUS=$(get_last_watchdog_status)
    
    # Track peak memory
    if [ "$CURRENT_MEMORY" -gt "$MEMORY_PEAK_MB" ]; then
        MEMORY_PEAK_MB=$CURRENT_MEMORY
    fi
    
    # Update running CPU average
    CPU_AVG=$(echo "scale=1; ($CPU_AVG * ($TOTAL_CHECKS - 1) + $CURRENT_CPU) / $TOTAL_CHECKS" | bc)
    
    # Determine status color
    if [[ "$WATCHDOG_STATUS" == *"critical"* ]]; then
        STATUS_COLOR=$RED
    elif [[ "$WATCHDOG_STATUS" == *"degraded"* ]]; then
        STATUS_COLOR=$YELLOW
    else
        STATUS_COLOR=$GREEN
    fi
    
    # Output to terminal
    echo -e "[${TIMESTAMP}] Check #${TOTAL_CHECKS} (${ELAPSED_MINUTES}min elapsed)"
    echo -e "  Memory: ${CURRENT_MEMORY}MB (peak: ${MEMORY_PEAK_MB}MB)"
    echo -e "  CPU: ${CURRENT_CPU}% (avg: ${CPU_AVG}%)"
    echo -e "  Critical alerts: ${CRITICAL_COUNT}"
    echo -e "  Warning alerts: ${WARNING_COUNT}"
    echo -e "  Watchdog status: ${STATUS_COLOR}${WATCHDOG_STATUS}${NC}"
    echo "  ---"
    
    # Write to output file
    cat >> "${OUTPUT_FILE}" << EOF
[${TIMESTAMP}] Check #${TOTAL_CHECKS} (${ELAPSED_MINUTES}min elapsed)
  Memory: ${CURRENT_MEMORY}MB (peak: ${MEMORY_PEAK_MB}MB)
  CPU: ${CURRENT_CPU}% (avg: ${CPU_AVG}%)
  Critical alerts: ${CRITICAL_COUNT}
  Warning alerts: ${WARNING_COUNT}
  Watchdog status: ${WATCHDOG_STATUS}
  
EOF
    
    # Check for critical conditions
    if [ "$CRITICAL_COUNT" -gt 10 ]; then
        echo -e "${RED}⚠️  HIGH CRITICAL ALERT COUNT DETECTED!${NC}"
        echo "Investigate immediately: tail -f logs/error_*.log"
    fi
    
    if [ "$CURRENT_MEMORY" -gt 1024 ]; then
        echo -e "${RED}⚠️  HIGH MEMORY USAGE: ${CURRENT_MEMORY}MB${NC}"
    fi
    
    # Sleep until next check
    sleep $CHECK_INTERVAL_SECONDS
done

# Generate summary report
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                    MONITORING COMPLETE                      ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Summary:"
echo "  Total checks: ${TOTAL_CHECKS}"
echo "  Duration: ${MONITOR_DURATION_HOURS} hours"
echo "  Peak memory: ${MEMORY_PEAK_MB}MB"
echo "  Average CPU: ${CPU_AVG}%"
echo "  Final critical alerts: ${CRITICAL_COUNT}"
echo "  Final warning alerts: ${WARNING_COUNT}"
echo ""
echo "Detailed log: ${OUTPUT_FILE}"
echo ""
echo "Recommendation:"
if [ "$CRITICAL_COUNT" -lt 5 ] && [ "$MEMORY_PEAK_MB" -lt 800 ]; then
    echo -e "${GREEN}✅ System stable - proceed to Phase 2${NC}"
else
    echo -e "${RED}❌ Issues detected - review logs before proceeding${NC}"
fi
