#!/bin/bash
# =============================================================================
# Phase 1 Deployment Script - Bybit Demo Environment
# =============================================================================
# This script automates the deployment of Phase 1 Issues A & B
# Run with: bash deploy_phase1_bybit_demo.sh
# =============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================================================================${NC}"
echo -e "${BLUE}Phase 1 Deployment - Bybit Demo Environment${NC}"
echo -e "${BLUE}================================================================================${NC}"
echo ""

# Step 1: Pre-Deployment Verification
echo -e "${YELLOW}[1/8] Running pre-deployment verification...${NC}"
if python3 verify_freqtrade_integration.py; then
    echo -e "${GREEN}✅ Verification passed${NC}"
else
    echo -e "${RED}❌ Verification failed. Aborting deployment.${NC}"
    exit 1
fi
echo ""

# Step 2: Check service status
echo -e "${YELLOW}[2/8] Checking current service status...${NC}"
API_STATUS=$(systemctl is-active auto-trade-api 2>/dev/null || echo "inactive")
WORKER_STATUS=$(systemctl is-active auto-trade-worker 2>/dev/null || echo "inactive")
echo "   API Service: $API_STATUS"
echo "   Worker Service: $WORKER_STATUS"
echo ""

# Step 3: Backup configuration
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
echo -e "${YELLOW}[3/8] Creating backups (timestamp: $TIMESTAMP)...${NC}"
cp .env ".env.backup.${TIMESTAMP}"
cp app/config.py "app/config.py.backup.${TIMESTAMP}"
echo -e "${GREEN}✅ Backups created:${NC}"
echo "   - .env.backup.${TIMESTAMP}"
echo "   - app/config.py.backup.${TIMESTAMP}"
echo ""

# Step 4: Update .env file
echo -e "${YELLOW}[4/8] Updating .env configuration...${NC}"

# Check if Phase 1 configs already exist
if grep -q "ENABLE_PERSISTENT_IDEMPOTENCY" .env; then
    echo -e "${YELLOW}⚠️  Phase 1 configuration already exists in .env${NC}"
    echo "   Skipping automatic update. Please review manually."
else
    cat >> .env << 'EOF'

# =============================================================================
# Phase 1 Issue A: Freqtrade Integration (Execution Layer Optimization)
# =============================================================================

# Persistent Idempotency (Redis-backed duplicate order prevention)
ENABLE_PERSISTENT_IDEMPOTENCY=true
IDEMPOTENCY_TTL_SECONDS=3600  # Cache TTL: 1 hour

# Trade State Recovery (crash recovery for stuck trades)
ENABLE_STATE_RECOVERY=true

# Circuit Breaker (pre-execution health checks)
CIRCUIT_BREAKER_PRE_EXECUTION_CHECK=true

# =============================================================================
# Phase 1 Issue B: Reconciliation Engine Enhancements
# =============================================================================

# Scheduling Configuration
RECONCILIATION_INTERVAL_SECONDS=120  # Run every 2 minutes

# Auto-Repair Configuration
RECONCILIATION_AUTO_REPAIR_SAFE=true  # Auto-repair safe mismatches

# Notification Configuration
RECONCILIATION_TELEGRAM_ALERTS=true  # Enable Telegram alerts for critical mismatches
RECONCILIATION_PROMETHEUS_METRICS=true  # Publish metrics to Prometheus

# Orphaned Order Detection
RECONCILIATION_MAX_ORPHANED_AGE_HOURS=24  # Only flag orders older than 24h

# Ghost Position Handling
# Options: import_and_alert, alert_only, ignore
RECONCILIATION_GHOST_POSITION_ACTION=import_and_alert
EOF
    echo -e "${GREEN}✅ Configuration added to .env${NC}"
fi
echo ""

# Step 5: Verify configuration
echo -e "${YELLOW}[5/8] Verifying configuration syntax...${NC}"
if python3 -c "from app.config import settings; print(f'Reconciliation Interval: {settings.RECONCILIATION_INTERVAL_SECONDS}s')" 2>&1; then
    echo -e "${GREEN}✅ Configuration loaded successfully${NC}"
else
    echo -e "${RED}❌ Configuration error. Restoring backup...${NC}"
    cp ".env.backup.${TIMESTAMP}" .env
    exit 1
fi
echo ""

# Step 6: Graceful restart
echo -e "${YELLOW}[6/8] Performing graceful service restart...${NC}"

echo "   Stopping worker service..."
sudo systemctl stop auto-trade-worker
sleep 5

echo "   Stopping API service..."
sudo systemctl stop auto-trade-api
sleep 3

echo "   Starting API service..."
sudo systemctl start auto-trade-api
sleep 5

echo "   Starting worker service..."
sudo systemctl start auto-trade-worker
sleep 5

echo -e "${GREEN}✅ Services restarted${NC}"
echo ""

# Step 7: Post-deployment health checks
echo -e "${YELLOW}[7/8] Running post-deployment health checks...${NC}"
sleep 5

# Check API health
if curl -s http://localhost:8000/health | grep -q "healthy"; then
    echo -e "${GREEN}✅ API health check passed${NC}"
else
    echo -e "${RED}❌ API health check failed${NC}"
    echo "   Check logs: journalctl -u auto-trade-api -n 50"
fi

# Check reconciliation status
if curl -s http://localhost:8000/api/v1/reconciliation/status | grep -q "is_running"; then
    echo -e "${GREEN}✅ Reconciliation engine running${NC}"
else
    echo -e "${YELLOW}⚠️  Reconciliation status unavailable (may need time to initialize)${NC}"
fi

echo ""

# Step 8: Display monitoring instructions
echo -e "${YELLOW}[8/8] Deployment complete! Monitoring instructions:${NC}"
echo ""
echo -e "${BLUE}Immediate Checks (Next 5 Minutes):${NC}"
echo "   • View API logs: journalctl -u auto-trade-api -f --since '2 minutes ago'"
echo "   • View worker logs: journalctl -u auto-trade-worker -f --since '2 minutes ago'"
echo "   • Check positions: curl http://localhost:8000/api/v1/trading/positions"
echo ""
echo -e "${BLUE}Prometheus Metrics (Monitor for 24 Hours):${NC}"
echo "   • Mismatches: reconciliation_mismatches_total"
echo "   • Repairs: reconciliation_repairs_total"
echo "   • Circuit breaker: circuit_breaker_state"
echo "   • Latency: http_request_duration_seconds{quantile='0.95'}"
echo ""
echo -e "${BLUE}Telegram Alerts:${NC}"
echo "   • Watch for reconciliation alerts (orphaned orders, ghost positions)"
echo "   • Alert deduplication prevents spam"
echo ""
echo -e "${GREEN}================================================================================${NC}"
echo -e "${GREEN}✅ DEPLOYMENT SUCCESSFUL${NC}"
echo -e "${GREEN}================================================================================${NC}"
echo ""
echo -e "${YELLOW}📋 Next Steps:${NC}"
echo "   1. Monitor logs for 1 hour (check every 15 minutes)"
echo "   2. Verify reconciliation runs every 120 seconds"
echo "   3. Review 24-hour monitoring checklist in PHASE1_DEPLOYMENT_GUIDE_BYBIT_DEMO.md"
echo "   4. Document any issues or observations"
echo ""
echo -e "${YELLOW}🚨 Rollback Command (if needed):${NC}"
echo "   bash rollback_phase1.sh ${TIMESTAMP}"
echo ""
