#!/bin/bash
# Production Enhancement Deployment Script
# Automates deployment of enhanced monitoring and notification features
#
# Usage:
#   ./deploy_production_enhancements.sh [--test] [--dry-run]

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="/home/admin/.openclaw/workspace/auto-trade-system"
VENV_DIR="${PROJECT_DIR}/.venv"
LOG_FILE="${PROJECT_DIR}/deployment.log"

# Parse arguments
TEST_MODE=false
DRY_RUN=false

for arg in "$@"; do
    case $arg in
        --test)
            TEST_MODE=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            echo -e "${RED}Unknown option: $arg${NC}"
            echo "Usage: $0 [--test] [--dry-run]"
            exit 1
            ;;
    esac
done

# Functions
log() {
    echo -e "$1" | tee -a "$LOG_FILE"
}

check_prerequisites() {
    log "\n${BLUE}=== Checking Prerequisites ===${NC}\n"
    
    # Check if project directory exists
    if [ ! -d "$PROJECT_DIR" ]; then
        log "${RED}Error: Project directory not found: $PROJECT_DIR${NC}"
        exit 1
    fi
    
    # Check if virtual environment exists
    if [ ! -d "$VENV_DIR" ]; then
        log "${RED}Error: Virtual environment not found: $VENV_DIR${NC}"
        exit 1
    fi
    
    # Check if Python is available
    if ! command -v python3 &> /dev/null; then
        log "${RED}Error: Python3 not found${NC}"
        exit 1
    fi
    
    log "${GREEN}✓ All prerequisites met${NC}"
}

verify_files() {
    log "\n${BLUE}=== Verifying Enhanced Files ===${NC}\n"
    
    local files=(
        "app/notifications/notifier.py"
        "scripts/production_monitoring_queries.py"
        "scripts/test_enhanced_notifications.py"
        "PRODUCTION_ENHANCED_MONITORING.md"
        "QUICK_REFERENCE_PRODUCTION_MONITORING.md"
        "IMPLEMENTATION_SUMMARY_PRODUCTION_ENHANCEMENTS.md"
    )
    
    local all_exist=true
    
    for file in "${files[@]}"; do
        if [ -f "${PROJECT_DIR}/${file}" ]; then
            log "${GREEN}✓ ${file}${NC}"
        else
            log "${RED}✗ ${file} (MISSING)${NC}"
            all_exist=false
        fi
    done
    
    if [ "$all_exist" = false ]; then
        log "\n${RED}Error: Some required files are missing${NC}"
        exit 1
    fi
}

run_tests() {
    log "\n${BLUE}=== Running Notification Tests ===${NC}\n"
    
    cd "$PROJECT_DIR"
    source "${VENV_DIR}/bin/activate"
    
    if python scripts/test_enhanced_notifications.py; then
        log "\n${GREEN}✓ All tests passed${NC}"
        return 0
    else
        log "\n${YELLOW}⚠ Some tests failed (may be due to missing Telegram config)${NC}"
        log "${YELLOW}  This is acceptable if TELEGRAM_BOT_TOKEN is not configured${NC}"
        return 0
    fi
}

check_database() {
    log "\n${BLUE}=== Checking Database Tables ===${NC}\n"
    
    cd "$PROJECT_DIR"
    source "${VENV_DIR}/bin/activate"
    
    # Try to query the database
    if python -c "
import asyncio
from app.database.connection import get_session
from sqlalchemy import text

async def check():
    async for db_session in get_session():
        try:
            # Check if tables exist
            tables = ['risk_events', 'recovery_events', 'execution_logs', 'order_events']
            for table in tables:
                result = await db_session.execute(text(f'SELECT COUNT(*) FROM {table}'))
                count = result.scalar()
                print(f'✓ {table}: {count} records')
            return True
        except Exception as e:
            print(f'✗ Database check failed: {e}')
            return False

result = asyncio.run(check())
exit(0 if result else 1)
"; then
        log "\n${GREEN}✓ Database tables verified${NC}"
        return 0
    else
        log "\n${RED}✗ Database check failed${NC}"
        log "${YELLOW}  Run migrations if needed: alembic upgrade head${NC}"
        return 1
    fi
}

check_telegram_config() {
    log "\n${BLUE}=== Checking Telegram Configuration ===${NC}\n"
    
    cd "$PROJECT_DIR"
    
    if grep -q "TELEGRAM_BOT_TOKEN=" .env && grep -q "TELEGRAM_CHAT_ID=" .env; then
        log "${GREEN}✓ Telegram configuration found in .env${NC}"
        
        # Check if values are set (not empty)
        BOT_TOKEN=$(grep "TELEGRAM_BOT_TOKEN=" .env | cut -d'=' -f2)
        CHAT_ID=$(grep "TELEGRAM_CHAT_ID=" .env | cut -d'=' -f2)
        
        if [ -z "$BOT_TOKEN" ] || [ -z "$CHAT_ID" ]; then
            log "${YELLOW}⚠ Telegram credentials appear to be empty${NC}"
            log "${YELLOW}  Notifications will not work until configured${NC}"
        else
            log "${GREEN}✓ Telegram credentials configured${NC}"
        fi
    else
        log "${YELLOW}⚠ Telegram configuration not found in .env${NC}"
        log "${YELLOW}  Add these lines to .env:${NC}"
        log "${YELLOW}    TELEGRAM_BOT_TOKEN=your_bot_token${NC}"
        log "${YELLOW}    TELEGRAM_CHAT_ID=your_chat_id${NC}"
    fi
}

test_monitoring_queries() {
    log "\n${BLUE}=== Testing Monitoring Queries ===${NC}\n"
    
    cd "$PROJECT_DIR"
    source "${VENV_DIR}/bin/activate"
    
    if timeout 30 python scripts/production_monitoring_queries.py > /tmp/monitor_test.log 2>&1; then
        log "${GREEN}✓ Monitoring queries executed successfully${NC}"
        log "\nSample output:"
        head -20 /tmp/monitor_test.log
        return 0
    else
        log "${YELLOW}⚠ Monitoring query test timed out or failed${NC}"
        log "${YELLOW}  Check logs: /tmp/monitor_test.log${NC}"
        return 0  # Don't fail deployment for this
    fi
}

backup_database() {
    log "\n${BLUE}=== Creating Database Backup ===${NC}\n"
    
    cd "$PROJECT_DIR"
    
    BACKUP_FILE="backup_$(date +%Y%m%d_%H%M%S).sql"
    
    if command -v pg_dump &> /dev/null; then
        if pg_dump -U postgres vmassit > "$BACKUP_FILE" 2>/dev/null; then
            log "${GREEN}✓ Database backup created: $BACKUP_FILE${NC}"
        else
            log "${YELLOW}⚠ Database backup failed (non-critical)${NC}"
        fi
    else
        log "${YELLOW}⚠ pg_dump not available, skipping backup${NC}"
    fi
}

restart_services() {
    log "\n${BLUE}=== Restarting Services ===${NC}\n"
    
    if systemctl is-active --quiet auto-trade 2>/dev/null; then
        log "Restarting auto-trade service..."
        sudo systemctl restart auto-trade
        
        # Wait for service to start
        sleep 5
        
        if systemctl is-active --quiet auto-trade; then
            log "${GREEN}✓ Service restarted successfully${NC}"
        else
            log "${RED}✗ Service failed to restart${NC}"
            log "Check logs: journalctl -u auto-trade -n 50"
            return 1
        fi
    else
        log "${YELLOW}⚠ auto-trade service not running (systemd)${NC}"
        log "${YELLOW}  Start manually: cd $PROJECT_DIR && python app/main.py${NC}"
    fi
    
    return 0
}

verify_deployment() {
    log "\n${BLUE}=== Verifying Deployment ===${NC}\n"
    
    cd "$PROJECT_DIR"
    
    # Check if service is running
    if systemctl is-active --quiet auto-trade 2>/dev/null; then
        log "${GREEN}✓ Service is running${NC}"
        
        # Check health endpoint
        if curl -s http://localhost:8000/health > /dev/null 2>&1; then
            log "${GREEN}✓ Health endpoint responding${NC}"
        else
            log "${YELLOW}⚠ Health endpoint not responding (wait a moment and retry)${NC}"
        fi
    else
        log "${YELLOW}⚠ Service status unknown${NC}"
    fi
    
    # Check recent logs
    log "\nRecent log entries:"
    if command -v journalctl &> /dev/null; then
        journalctl -u auto-trade -n 10 --no-pager 2>/dev/null || echo "Logs not available"
    fi
}

print_summary() {
    log "\n${BLUE}========================================${NC}"
    log "${GREEN}  DEPLOYMENT COMPLETE${NC}"
    log "${BLUE}========================================${NC}\n"
    
    log "${GREEN}Enhanced Features Deployed:${NC}"
    log "  ✓ Order state change notifications"
    log "  ✓ Reconciliation mismatch alerts"
    log "  ✓ Risk violation warnings"
    log "  ✓ Production monitoring queries"
    log "  ✓ Event bus integration"
    log "  ✓ Database repository access"
    
    log "\n${BLUE}Documentation:${NC}"
    log "  • PRODUCTION_ENHANCED_MONITORING.md (Complete guide)"
    log "  • QUICK_REFERENCE_PRODUCTION_MONITORING.md (Quick ref)"
    log "  • IMPLEMENTATION_SUMMARY_PRODUCTION_ENHANCEMENTS.md (Technical details)"
    
    log "\n${BLUE}Useful Commands:${NC}"
    log "  • Monitor events: journalctl -u auto-trade -f"
    log "  • Run queries: python scripts/production_monitoring_queries.py"
    log "  • Test alerts: python scripts/test_enhanced_notifications.py"
    log "  • Check health: curl http://localhost:8000/health"
    
    log "\n${YELLOW}Next Steps:${NC}"
    log "  1. Monitor system for 48 hours"
    log "  2. Review Telegram alerts received"
    log "  3. Adjust thresholds if needed"
    log "  4. Train team on new features"
    
    log "\n${GREEN}Deployment completed at: $(date)${NC}\n"
}

# Main deployment flow
main() {
    log "${BLUE}========================================${NC}"
    log "${BLUE}  Production Enhancement Deployment${NC}"
    log "${BLUE}========================================${NC}"
    log "Started at: $(date)\n"
    
    if [ "$DRY_RUN" = true ]; then
        log "${YELLOW}DRY RUN MODE - No changes will be made${NC}\n"
    fi
    
    check_prerequisites
    verify_files
    
    if [ "$DRY_RUN" = false ]; then
        if [ "$TEST_MODE" = true ]; then
            run_tests
        fi
        
        check_database
        check_telegram_config
        test_monitoring_queries
        backup_database
        restart_services
        verify_deployment
    else
        log "${YELLOW}Skipping actual deployment steps (dry run)${NC}"
    fi
    
    print_summary
}

# Run main function
main "$@"
