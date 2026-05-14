#!/bin/bash
#
# Enterprise v3.0.0 Systemd Installation Guide
# This script provides step-by-step instructions for installing systemd services
#

set -e

WORKSPACE="/home/admin/.openclaw/workspace/auto-trade-system"
VENV_PYTHON="$WORKSPACE/.venv/bin/python"

echo "=========================================="
echo "  Enterprise v3.0.0 Systemd Installation"
echo "=========================================="
echo ""
echo "This script will:"
echo "  1. Stop currently running processes"
echo "  2. Install systemd service files"
echo "  3. Enable auto-start on boot"
echo "  4. Start both services"
echo "  5. Verify everything is working"
echo ""
read -p "Continue? (y/n): " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Installation cancelled."
    exit 1
fi
echo ""

# Step 1: Stop current processes
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 1: Stopping current processes..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Find and stop uvicorn processes
UVICORN_PIDS=$(pgrep -f "uvicorn app.main:app" || true)
if [ -n "$UVICORN_PIDS" ]; then
    echo "Found uvicorn processes: $UVICORN_PIDS"
    kill $UVICORN_PIDS 2>/dev/null || true
    sleep 2
    # Force kill if still running
    kill -9 $UVICORN_PIDS 2>/dev/null || true
    echo "✅ Uvicorn processes stopped"
else
    echo "ℹ️  No uvicorn processes found"
fi

# Find and stop worker processes
WORKER_PIDS=$(pgrep -f "worker_gold_bot" || true)
if [ -n "$WORKER_PIDS" ]; then
    echo "Found worker processes: $WORKER_PIDS"
    kill $WORKER_PIDS 2>/dev/null || true
    sleep 2
    kill -9 $WORKER_PIDS 2>/dev/null || true
    echo "✅ Worker processes stopped"
else
    echo "ℹ️  No worker processes found"
fi

sleep 2
echo ""

# Step 2: Install service files
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 2: Installing systemd service files..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

sudo cp $WORKSPACE/systemd/auto-trade-api.service /etc/systemd/system/
sudo cp $WORKSPACE/systemd/auto-trade-worker.service /etc/systemd/system/

echo "✅ Service files copied to /etc/systemd/system/"
ls -lh /etc/systemd/system/auto-trade-*.service
echo ""

# Step 3: Reload systemd daemon
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 3: Reloading systemd daemon..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

sudo systemctl daemon-reload
echo "✅ Systemd daemon reloaded"
echo ""

# Step 4: Enable services
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 4: Enabling services for auto-start..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

sudo systemctl enable auto-trade-api.service
sudo systemctl enable auto-trade-worker.service
echo "✅ Services enabled (will start on boot)"
echo ""

# Step 5: Start services
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 5: Starting services..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "Starting API service..."
sudo systemctl start auto-trade-api.service
sleep 3

echo "Starting Worker service..."
sudo systemctl start auto-trade-worker.service
sleep 3

echo "✅ Both services started"
echo ""

# Step 6: Verify services
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 6: Verifying services..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "API Service Status:"
sudo systemctl status auto-trade-api.service --no-pager -l | head -20
echo ""

echo "Worker Service Status:"
sudo systemctl status auto-trade-worker.service --no-pager -l | head -20
echo ""

# Check if active
API_STATUS=$(sudo systemctl is-active auto-trade-api.service)
WORKER_STATUS=$(sudo systemctl is-active auto-trade-worker.service)

echo "Service States:"
echo "  API Service:    $API_STATUS"
echo "  Worker Service: $WORKER_STATUS"
echo ""

if [ "$API_STATUS" == "active" ] && [ "$WORKER_STATUS" == "active" ]; then
    echo "✅ Both services are running!"
else
    echo "⚠️  Warning: One or more services may not be running properly"
    echo "Check logs with: journalctl -u auto-trade-api -f"
fi
echo ""

# Step 7: Test endpoints
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 7: Testing API endpoints..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

sleep 5  # Give services time to fully initialize

echo "Testing health endpoint..."
HEALTH_RESPONSE=$(curl -s http://localhost:8000/health/deep 2>/dev/null || echo "FAILED")
if [ "$HEALTH_RESPONSE" != "FAILED" ]; then
    echo "✅ Health endpoint responding"
    echo "$HEALTH_RESPONSE" | python3 -m json.tool 2>/dev/null | head -10 || echo "$HEALTH_RESPONSE"
else
    echo "❌ Health endpoint not responding"
    echo "Check logs: journalctl -u auto-trade-api -n 50"
fi
echo ""

# Step 8: Show log locations
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 8: Log file locations..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "Systemd Journal Logs:"
echo "  API:     journalctl -u auto-trade-api -f"
echo "  Worker:  journalctl -u auto-trade-worker -f"
echo "  Both:    journalctl -u auto-trade-api -u auto-trade-worker -f"
echo ""

echo "File Logs (if configured in logging_config.py):"
echo "  Directory: $WORKSPACE/logs/"
ls -lh $WORKSPACE/logs/*.log 2>/dev/null | tail -5 || echo "  No log files yet"
echo ""

# Final summary
echo "=========================================="
echo "  Installation Complete! ✅"
echo "=========================================="
echo ""
echo "Quick Reference:"
echo "  • Status:   sudo systemctl status auto-trade-api auto-trade-worker"
echo "  • Logs:     journalctl -u auto-trade-api -f"
echo "  • Restart:  sudo systemctl restart auto-trade-api auto-trade-worker"
echo "  • Stop:     sudo systemctl stop auto-trade-api auto-trade-worker"
echo "  • Disable:  sudo systemctl disable auto-trade-api auto-trade-worker"
echo ""
echo "Admin API Key:"
grep ADMIN_API_KEY $WORKSPACE/.env | head -1
echo ""
echo "Test Admin Endpoint:"
ADMIN_KEY=$(grep ADMIN_API_KEY $WORKSPACE/.env | cut -d= -f2 | head -1)
echo "  curl -H \"x-api-key: $ADMIN_KEY\" http://localhost:8000/admin/state | jq"
echo ""
echo "Next Steps:"
echo "  1. Set up log rotation (see SYSTEMD_FIX_SUMMARY.md)"
echo "  2. Test admin endpoints"
echo "  3. Monitor logs for any issues"
echo ""
