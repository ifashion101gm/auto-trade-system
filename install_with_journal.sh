#!/bin/bash
#
# Install Systemd Services (Journal Logging Version)
# Run with: sudo ./install_with_journal.sh
#

set -e

WORKSPACE="/home/admin/.openclaw/workspace/auto-trade-system"

echo "=========================================="
echo "  Installing Systemd Services"
echo "  (Journal Logging Mode)"
echo "=========================================="
echo ""

# Step 1: Stop any running processes
echo "Step 1: Stopping current processes..."
pkill -f "uvicorn app.main:app" 2>/dev/null || true
pkill -f "worker_gold_bot" 2>/dev/null || true
sleep 2
echo "✅ Processes stopped"
echo ""

# Step 2: Copy service files
echo "Step 2: Installing service files..."
sudo cp $WORKSPACE/systemd/auto-trade-api.service /etc/systemd/system/
sudo cp $WORKSPACE/systemd/auto-trade-worker.service /etc/systemd/system/
echo "✅ Service files installed"
echo ""

# Step 3: Reload systemd
echo "Step 3: Reloading systemd daemon..."
sudo systemctl daemon-reload
echo "✅ Daemon reloaded"
echo ""

# Step 4: Verify service files are valid
echo "Step 4: Verifying service files..."
API_VERIFY=$(sudo systemd-analyze verify /etc/systemd/system/auto-trade-api.service 2>&1 || true)
WORKER_VERIFY=$(sudo systemd-analyze verify /etc/systemd/system/auto-trade-worker.service 2>&1 || true)

if [ -z "$API_VERIFY" ]; then
    echo "✅ API service file is valid"
else
    echo "⚠️  API service warnings:"
    echo "$API_VERIFY"
fi

if [ -z "$WORKER_VERIFY" ]; then
    echo "✅ Worker service file is valid"
else
    echo "⚠️  Worker service warnings:"
    echo "$WORKER_VERIFY"
fi
echo ""

# Step 5: Enable services
echo "Step 5: Enabling services for auto-start..."
sudo systemctl enable auto-trade-api.service
sudo systemctl enable auto-trade-worker.service
echo "✅ Services enabled"
echo ""

# Step 6: Start services
echo "Step 6: Starting services..."
sudo systemctl start auto-trade-api.service
sleep 3
sudo systemctl start auto-trade-worker.service
sleep 3
echo "✅ Services started"
echo ""

# Step 7: Check status
echo "Step 7: Checking service status..."
echo ""
echo "API Service:"
sudo systemctl status auto-trade-api.service --no-pager -l | head -15
echo ""
echo "Worker Service:"
sudo systemctl status auto-trade-worker.service --no-pager -l | head -15
echo ""

# Step 8: Verify they're active
API_STATUS=$(sudo systemctl is-active auto-trade-api.service)
WORKER_STATUS=$(sudo systemctl is-active auto-trade-worker.service)

echo "Service States:"
echo "  API Service:    $API_STATUS"
echo "  Worker Service: $WORKER_STATUS"
echo ""

if [ "$API_STATUS" == "active" ] && [ "$WORKER_STATUS" == "active" ]; then
    echo "✅ Both services are running!"
else
    echo "⚠️  Warning: Services may not be running properly"
    echo ""
    echo "Check logs:"
    echo "  API:    journalctl -u auto-trade-api -n 50"
    echo "  Worker: journalctl -u auto-trade-worker -n 50"
fi
echo ""

# Step 9: Test API endpoint
echo "Step 9: Testing API endpoint..."
sleep 5
HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health/deep 2>/dev/null || echo "FAILED")

if [ "$HEALTH" == "200" ]; then
    echo "✅ API endpoint responding (HTTP 200)"
    echo ""
    echo "Health check:"
    curl -s http://localhost:8000/health/deep | python3 -m json.tool 2>/dev/null | head -10 || true
else
    echo "❌ API endpoint not responding (HTTP $HEALTH)"
    echo ""
    echo "Check API logs:"
    sudo journalctl -u auto-trade-api -n 30 --no-pager
fi
echo ""

# Summary
echo "=========================================="
echo "  Installation Complete!"
echo "=========================================="
echo ""
echo "Logging Configuration:"
echo "  • Using systemd journal (native logging)"
echo "  • Application also writes to files via logging_config.py"
echo ""
echo "View Logs:"
echo "  • API live:    journalctl -u auto-trade-api -f"
echo "  • Worker live: journalctl -u auto-trade-worker -f"
echo "  • Both live:   journalctl -u auto-trade-api -u auto-trade-worker -f"
echo "  • Last 50:     journalctl -u auto-trade-api -n 50"
echo ""
echo "Management:"
echo "  • Status:   sudo systemctl status auto-trade-api auto-trade-worker"
echo "  • Restart:  sudo systemctl restart auto-trade-api auto-trade-worker"
echo "  • Stop:     sudo systemctl stop auto-trade-api auto-trade-worker"
echo ""
echo "Admin API Key:"
grep ADMIN_API_KEY $WORKSPACE/.env | head -1
echo ""
echo "Test Admin Endpoint:"
ADMIN_KEY=$(grep ADMIN_API_KEY $WORKSPACE/.env | cut -d= -f2 | head -1)
echo "  curl -H \"x-api-key: $ADMIN_KEY\" http://localhost:8000/admin/state | jq"
echo ""
