#!/bin/bash
# MEXC Order Handling Fix - Deployment Script
# This script automates the deployment of the MEXC order handling fixes.

set -e  # Exit on error

echo "=========================================="
echo "MEXC Order Handling Fix - Deployment"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print status
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Step 1: Pre-deployment checks
echo "Step 1: Pre-deployment Checks"
echo "------------------------------"

# Check if we're in the right directory
if [ ! -f "app/main.py" ]; then
    print_error "Not in project root directory. Please run from /path/to/auto-trade-system"
    exit 1
fi
print_status "Project directory verified"

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
print_status "Python version: $PYTHON_VERSION"

# Check if virtual environment exists
if [ -d ".venv" ]; then
    print_status "Virtual environment found"
else
    print_warning "No virtual environment found. Creating one..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install --upgrade pip
fi

# Activate virtual environment
source .venv/bin/activate
print_status "Virtual environment activated"

# Step 2: Backup
echo ""
echo "Step 2: Database Backup"
echo "-----------------------"

if [ -f "scripts/backup_database.sh" ]; then
    print_warning "Creating database backup..."
    bash scripts/backup_database.sh
    print_status "Database backup completed"
else
    print_warning "Backup script not found. Skipping backup."
fi

# Step 3: Install dependencies
echo ""
echo "Step 3: Install Dependencies"
echo "----------------------------"

print_status "Installing/updating dependencies..."
pip install -r requirements.txt
print_status "Dependencies installed"

# Step 4: Run tests
echo ""
echo "Step 4: Run Validation Tests"
echo "----------------------------"

if [ -f "scripts/test_mexc_order_handling.py" ]; then
    print_status "Running MEXC order handling tests..."
    python scripts/test_mexc_order_handling.py
    
    TEST_RESULT=$?
    if [ $TEST_RESULT -eq 0 ]; then
        print_status "All tests passed!"
    else
        print_error "Tests failed! Aborting deployment."
        exit 1
    fi
else
    print_warning "Test script not found. Skipping tests."
fi

# Step 5: Configuration check
echo ""
echo "Step 5: Configuration Check"
echo "---------------------------"

if [ -f ".env" ]; then
    print_status ".env file found"
    
    # Check for required variables
    if grep -q "MEXC_API_KEY=" .env && grep -q "MEXC_API_SECRET=" .env; then
        print_status "MEXC API credentials configured"
    else
        print_error "MEXC API credentials missing in .env file"
        exit 1
    fi
else
    print_error ".env file not found!"
    exit 1
fi

# Step 6: Stop services (if running)
echo ""
echo "Step 6: Stop Services"
echo "---------------------"

if command -v systemctl &> /dev/null; then
    print_warning "Stopping vmassit service..."
    sudo systemctl stop vmassit || true
    print_status "Service stopped"
else
    print_warning "systemctl not available. Manual restart may be needed."
fi

# Step 7: Verify new files exist
echo ""
echo "Step 7: Verify New Files"
echo "------------------------"

NEW_FILES=(
    "app/exchange/mexc_executor.py"
    "app/services/position_sync.py"
    "scripts/test_mexc_order_handling.py"
    "MEXC_ORDER_HANDLING_FIX.md"
    "MEXC_QUICK_REFERENCE.md"
    "MEXC_IMPLEMENTATION_SUMMARY.md"
)

for file in "${NEW_FILES[@]}"; do
    if [ -f "$file" ]; then
        print_status "$file exists"
    else
        print_error "$file not found!"
        exit 1
    fi
done

# Step 8: Start services
echo ""
echo "Step 8: Start Services"
echo "----------------------"

if command -v systemctl &> /dev/null; then
    print_status "Starting vmassit service..."
    sudo systemctl start vmassit
    print_status "Service started"
    
    # Wait a moment for service to initialize
    sleep 3
    
    # Check service status
    if sudo systemctl is-active --quiet vmassit; then
        print_status "Service is running"
    else
        print_error "Service failed to start!"
        sudo systemctl status vmassit
        exit 1
    fi
else
    print_warning "systemctl not available. Please start services manually:"
    echo "   cd /path/to/auto-trade-system"
    echo "   source .venv/bin/activate"
    echo "   uvicorn app.main:app --host 0.0.0.0 --port 8000"
fi

# Step 9: Post-deployment verification
echo ""
echo "Step 9: Post-Deployment Verification"
echo "------------------------------------"

print_status "Checking logs for errors..."
sleep 2

if [ -f "/var/log/vmassit/app.log" ]; then
    ERROR_COUNT=$(tail -100 /var/log/vmassit/app.log | grep -c "ERROR" || true)
    if [ $ERROR_COUNT -eq 0 ]; then
        print_status "No errors found in recent logs"
    else
        print_warning "Found $ERROR_COUNT error(s) in recent logs"
        print_warning "Review logs: tail -f /var/log/vmassit/app.log"
    fi
else
    print_warning "Log file not found at /var/log/vmassit/app.log"
fi

# Check if position sync started
if [ -f "/var/log/vmassit/app.log" ]; then
    if grep -q "Position sync started" /var/log/vmassit/app.log; then
        print_status "Position sync service started successfully"
    else
        print_warning "Position sync service may not have started. Check logs."
    fi
fi

# Step 10: Summary
echo ""
echo "=========================================="
echo "Deployment Summary"
echo "=========================================="
echo ""
print_status "Deployment completed successfully!"
echo ""
echo "Next Steps:"
echo "1. Monitor logs: tail -f /var/log/vmassit/app.log"
echo "2. Run health check: curl http://localhost:8000/api/health"
echo "3. Execute test trade: python scripts/execute_gold_trade.py --testnet --amount 0.001"
echo "4. Review documentation: cat MEXC_QUICK_REFERENCE.md"
echo ""
echo "Important:"
echo "- Monitor the system for the first 10 minutes"
echo "- Watch for any ERROR or CRITICAL messages in logs"
echo "- Verify position sync is working (should see 'Position sync' messages)"
echo "- Test with small trades before scaling up"
echo ""
print_status "Happy Trading! 🚀"
echo ""
