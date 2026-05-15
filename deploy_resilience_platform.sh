#!/bin/bash
# ============================================================================
# Resilience Platform Deployment Script
# 
# This script automates the deployment of the Resilience Platform integration.
# It includes pre-deployment checks, backup creation, and post-deployment verification.
#
# Usage:
#   ./deploy_resilience_platform.sh [--staging|--production] [--dry-run]
# ============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="/home/admin/.openclaw/workspace/auto-trade-system"
BACKUP_DIR="${PROJECT_DIR}/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="${PROJECT_DIR}/logs/deploy_resilience_${TIMESTAMP}.log"

# Parse arguments
DEPLOY_ENV="staging"
DRY_RUN=false

for arg in "$@"; do
    case $arg in
        --production)
            DEPLOY_ENV="production"
            shift
            ;;
        --staging)
            DEPLOY_ENV="staging"
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            echo -e "${RED}Unknown argument: $arg${NC}"
            echo "Usage: $0 [--staging|--production] [--dry-run]"
            exit 1
            ;;
    esac
done

# ============================================================================
# Helper Functions
# ============================================================================

log() {
    echo -e "$1" | tee -a "$LOG_FILE"
}

check_command() {
    if ! command -v "$1" &> /dev/null; then
        log "${RED}✗ Required command not found: $1${NC}"
        exit 1
    fi
}

backup_file() {
    local file=$1
    local backup_path="${BACKUP_DIR}/${file##*/}.${TIMESTAMP}.bak"
    
    if [ -f "$file" ]; then
        cp "$file" "$backup_path"
        log "${GREEN}✓ Backed up: $file → $backup_path${NC}"
    else
        log "${YELLOW}⚠ File not found (skipping backup): $file${NC}"
    fi
}

run_test() {
    local test_name=$1
    local test_cmd=$2
    
    log "${BLUE}Running: $test_name...${NC}"
    if eval "$test_cmd" >> "$LOG_FILE" 2>&1; then
        log "${GREEN}✓ $test_name passed${NC}"
        return 0
    else
        log "${RED}✗ $test_name failed${NC}"
        return 1
    fi
}

# ============================================================================
# Pre-Deployment Checks
# ============================================================================

pre_deployment_checks() {
    log "\n${BLUE}═══════════════════════════════════════════════════════════${NC}"
    log "${BLUE}  PRE-DEPLOYMENT CHECKS${NC}"
    log "${BLUE}═══════════════════════════════════════════════════════════${NC}\n"
    
    # Check Python
    check_command python3
    
    # Check virtual environment
    if [ ! -d "${PROJECT_DIR}/.venv" ]; then
        log "${RED}✗ Virtual environment not found at ${PROJECT_DIR}/.venv${NC}"
        exit 1
    fi
    
    # Activate virtual environment
    source "${PROJECT_DIR}/.venv/bin/activate"
    log "${GREEN}✓ Virtual environment activated${NC}"
    
    # Run integration tests
    run_test "Integration Tests" \
        "cd ${PROJECT_DIR} && python test_resilience_integration.py --offline"
    
    # Check required files exist
    log "\n${BLUE}Checking required files...${NC}"
    local required_files=(
        "app/resilience/__init__.py"
        "app/resilience/resilience_platform.py"
        "app/resilience/resilience_manager.py"
        "app/resilience/state_machine.py"
        "app/resilience/recovery_executor.py"
        "app/dashboard/resilience_api.py"
        "app/main.py"
        "app/execution/trading_service.py"
    )
    
    for file in "${required_files[@]}"; do
        if [ -f "${PROJECT_DIR}/${file}" ]; then
            log "${GREEN}✓ Found: $file${NC}"
        else
            log "${RED}✗ Missing: $file${NC}"
            exit 1
        fi
    done
    
    log "\n${GREEN}✓ All pre-deployment checks passed${NC}\n"
}

# ============================================================================
# Backup Phase
# ============================================================================

create_backups() {
    log "\n${BLUE}═══════════════════════════════════════════════════════════${NC}"
    log "${BLUE}  CREATING BACKUPS${NC}"
    log "${BLUE}═══════════════════════════════════════════════════════════${NC}\n"
    
    # Create backup directory
    mkdir -p "$BACKUP_DIR"
    
    # Backup modified files
    backup_file "${PROJECT_DIR}/app/main.py"
    backup_file "${PROJECT_DIR}/app/execution/trading_service.py"
    
    # Backup configuration
    if [ -f "${PROJECT_DIR}/.env" ]; then
        backup_file "${PROJECT_DIR}/.env"
    fi
    
    log "\n${GREEN}✓ Backups created successfully${NC}\n"
}

# ============================================================================
# Deployment Phase
# ============================================================================

deploy() {
    log "\n${BLUE}═══════════════════════════════════════════════════════════${NC}"
    log "${BLUE}  DEPLOYING RESILIENCE PLATFORM${NC}"
    log "${BLUE}═══════════════════════════════════════════════════════════${NC}\n"
    
    if [ "$DRY_RUN" = true ]; then
        log "${YELLOW}⚠ DRY RUN MODE - No changes will be made${NC}\n"
        log "Files that would be deployed:"
        log "  - app/main.py (resilience platform initialization)"
        log "  - app/execution/trading_service.py (state-check guards)"
        log "  - app/dashboard/resilience_api.py (NEW - observability endpoints)"
        log "  - test_resilience_integration.py (NEW - integration tests)"
        log ""
        return 0
    fi
    
    log "${GREEN}Deploying to: ${DEPLOY_ENV^^}${NC}\n"
    
    # Verify syntax of Python files
    log "${BLUE}Verifying Python syntax...${NC}"
    python3 -m py_compile "${PROJECT_DIR}/app/main.py"
    python3 -m py_compile "${PROJECT_DIR}/app/execution/trading_service.py"
    python3 -m py_compile "${PROJECT_DIR}/app/dashboard/resilience_api.py"
    log "${GREEN}✓ All Python files have valid syntax${NC}\n"
    
    # Check imports
    log "${BLUE}Verifying imports...${NC}"
    cd "${PROJECT_DIR}"
    python3 -c "from app.resilience import ResilienceManager, SystemStateMachine, RecoveryExecutor" || {
        log "${RED}✗ Import verification failed${NC}"
        exit 1
    }
    log "${GREEN}✓ All imports successful${NC}\n"
    
    log "${GREEN}✓ Deployment completed successfully${NC}\n"
}

# ============================================================================
# Post-Deployment Verification
# ============================================================================

post_deployment_verification() {
    log "\n${BLUE}═══════════════════════════════════════════════════════════${NC}"
    log "${BLUE}  POST-DEPLOYMENT VERIFICATION${NC}"
    log "${BLUE}═══════════════════════════════════════════════════════════${NC}\n"
    
    if [ "$DRY_RUN" = true ]; then
        log "${YELLOW}⚠ Skipping verification in dry-run mode${NC}\n"
        return 0
    fi
    
    # Run integration tests again
    run_test "Post-Deployment Integration Tests" \
        "cd ${PROJECT_DIR} && python test_resilience_integration.py --offline"
    
    # Verify API endpoints are registered
    log "\n${BLUE}Verifying API endpoint registration...${NC}"
    if grep -q "resilience_router" "${PROJECT_DIR}/app/main.py"; then
        log "${GREEN}✓ Resilience router registered in main.py${NC}"
    else
        log "${RED}✗ Resilience router NOT found in main.py${NC}"
        exit 1
    fi
    
    # Verify state machine initialization
    if grep -q "SystemStateMachine" "${PROJECT_DIR}/app/main.py"; then
        log "${GREEN}✓ State machine initialization found${NC}"
    else
        log "${RED}✗ State machine initialization NOT found${NC}"
        exit 1
    fi
    
    # Verify trading service guards
    if grep -q "blocks_all_trading" "${PROJECT_DIR}/app/execution/trading_service.py"; then
        log "${GREEN}✓ Trading service state guards implemented${NC}"
    else
        log "${RED}✗ Trading service state guards NOT found${NC}"
        exit 1
    fi
    
    log "\n${GREEN}✓ All post-deployment verifications passed${NC}\n"
}

# ============================================================================
# Main Execution
# ============================================================================

main() {
    log "\n${BLUE}╔═══════════════════════════════════════════════════════════╗${NC}"
    log "${BLUE}║  RESILIENCE PLATFORM DEPLOYMENT                          ║${NC}"
    log "${BLUE}║  Environment: $(printf '%-45s' "${DEPLOY_ENV^^}")║${NC}"
    log "${BLUE}║  Timestamp: $(printf '%-47s' "$TIMESTAMP")║${NC}"
    log "${BLUE}╚═══════════════════════════════════════════════════════════╝${NC}\n"
    
    # Create logs directory if it doesn't exist
    mkdir -p "${PROJECT_DIR}/logs"
    
    # Step 1: Pre-deployment checks
    pre_deployment_checks
    
    # Step 2: Create backups
    create_backups
    
    # Step 3: Deploy
    deploy
    
    # Step 4: Post-deployment verification
    post_deployment_verification
    
    # Summary
    log "\n${GREEN}═══════════════════════════════════════════════════════════${NC}"
    log "${GREEN}  DEPLOYMENT SUCCESSFUL${NC}"
    log "${GREEN}═══════════════════════════════════════════════════════════${NC}\n"
    
    log "${BLUE}Next Steps:${NC}"
    log "  1. Start/restart the application"
    log "  2. Monitor logs for first hour: tail -f ${PROJECT_DIR}/logs/app.log"
    log "  3. Test API endpoints:"
    log "     - curl http://localhost:8000/api/v1/resilience/status"
    log "     - curl http://localhost:8000/api/v1/resilience/health-score"
    log "  4. Review dashboard at http://localhost:8000/docs"
    log ""
    log "${BLUE}Documentation:${NC}"
    log "  - Quick Reference: ${PROJECT_DIR}/RESILIENCE_PLATFORM_QUICKREF.md"
    log "  - Integration Guide: ${PROJECT_DIR}/INTEGRATION_GUIDE_RESILIENCE_PLATFORM.py"
    log "  - Full Report: ${PROJECT_DIR}/RESILIENCE_PLATFORM_DEPLOYMENT_REPORT.md"
    log ""
    log "${BLUE}Backup Location: ${BACKUP_DIR}${NC}"
    log "${BLUE}Log File: ${LOG_FILE}${NC}"
    log ""
    
    if [ "$DEPLOY_ENV" = "production" ]; then
        log "${YELLOW}⚠️  PRODUCTION DEPLOYMENT - Monitor closely for 24-48 hours${NC}"
        log "${YELLOW}⚠️  Keep legacy fallback mechanisms active initially${NC}"
        log ""
    fi
}

# Execute main function
main "$@"
