#!/bin/bash
# =============================================================================
# Phase 1 Rollback Script - Bybit Demo Environment
# =============================================================================
# Usage: bash rollback_phase1.sh [BACKUP_TIMESTAMP]
# Example: bash rollback_phase1.sh 20260515_143022
# If no timestamp provided, uses most recent backup
# =============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${RED}================================================================================${NC}"
echo -e "${RED}Phase 1 Rollback - Bybit Demo Environment${NC}"
echo -e "${RED}================================================================================${NC}"
echo ""

# Get backup timestamp
if [ -z "$1" ]; then
    echo -e "${YELLOW}No timestamp provided. Finding most recent backup...${NC}"
    LATEST_BACKUP=$(ls -t .env.backup.* 2>/dev/null | head -1)
    if [ -z "$LATEST_BACKUP" ]; then
        echo -e "${RED}❌ No backups found. Cannot rollback.${NC}"
        exit 1
    fi
    TIMESTAMP=$(basename "$LATEST_BACKUP" | sed 's/.env.backup.//')
    echo -e "${GREEN}Using most recent backup: $TIMESTAMP${NC}"
else
    TIMESTAMP="$1"
fi

echo ""
echo -e "${YELLOW}Rolling back to backup from: $TIMESTAMP${NC}"
echo ""

# Confirm rollback
read -p "Are you sure you want to rollback? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo -e "${YELLOW}Rollback cancelled.${NC}"
    exit 0
fi
echo ""

# Step 1: Stop services
echo -e "${YELLOW}[1/5] Stopping services...${NC}"
sudo systemctl stop auto-trade-api auto-trade-worker
sleep 3
echo -e "${GREEN}✅ Services stopped${NC}"
echo ""

# Step 2: Restore .env
echo -e "${YELLOW}[2/5] Restoring .env configuration...${NC}"
if [ -f ".env.backup.${TIMESTAMP}" ]; then
    cp ".env.backup.${TIMESTAMP}" .env
    echo -e "${GREEN}✅ .env restored from .env.backup.${TIMESTAMP}${NC}"
else
    echo -e "${RED}❌ Backup file not found: .env.backup.${TIMESTAMP}${NC}"
    echo "   Available backups:"
    ls -lh .env.backup.* 2>/dev/null || echo "   No backups found"
    exit 1
fi
echo ""

# Step 3: Restore config.py (if backup exists)
echo -e "${YELLOW}[3/5] Checking config.py backup...${NC}"
if [ -f "app/config.py.backup.${TIMESTAMP}" ]; then
    cp "app/config.py.backup.${TIMESTAMP}" app/config.py
    echo -e "${GREEN}✅ config.py restored from app/config.py.backup.${TIMESTAMP}${NC}"
else
    echo -e "${YELLOW}⚠️  No config.py backup found for this timestamp. Keeping current version.${NC}"
fi
echo ""

# Step 4: Restart services
echo -e "${YELLOW}[4/5] Restarting services...${NC}"
sudo systemctl start auto-trade-api
sleep 5
sudo systemctl start auto-trade-worker
sleep 5
echo -e "${GREEN}✅ Services restarted${NC}"
echo ""

# Step 5: Verify rollback
echo -e "${YELLOW}[5/5] Verifying rollback...${NC}"
sleep 5

# Check API health
if curl -s http://localhost:8000/health | grep -q "healthy"; then
    echo -e "${GREEN}✅ API health check passed${NC}"
else
    echo -e "${RED}❌ API health check failed${NC}"
    echo "   Check logs: journalctl -u auto-trade-api -n 50"
fi

# Check service status
API_STATUS=$(systemctl is-active auto-trade-api)
WORKER_STATUS=$(systemctl is-active auto-trade-worker)
echo "   API Service: $API_STATUS"
echo "   Worker Service: $WORKER_STATUS"

echo ""
echo -e "${GREEN}================================================================================${NC}"
echo -e "${GREEN}✅ ROLLBACK COMPLETE${NC}"
echo -e "${GREEN}================================================================================${NC}"
echo ""
echo -e "${YELLOW}📋 Post-Rollback Checks:${NC}"
echo "   1. Verify open positions unchanged"
echo "   2. Check trading operations normal"
echo "   3. Review logs for any errors"
echo "   4. Document reason for rollback"
echo ""
echo -e "${YELLOW}🔍 Useful Commands:${NC}"
echo "   • View recent logs: journalctl -u auto-trade-api -n 100"
echo "   • Check positions: curl http://localhost:8000/api/v1/trading/positions"
echo "   • System status: systemctl status auto-trade-api auto-trade-worker"
echo ""
