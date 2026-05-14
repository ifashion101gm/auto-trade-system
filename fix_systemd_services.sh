#!/bin/bash
#
# Fix systemd service files and install them
# Run this script with: sudo ./fix_systemd_services.sh
#

set -e

WORKSPACE="/home/admin/.openclaw/workspace/auto-trade-system"

echo "=========================================="
echo "  Fixing Systemd Service Files"
echo "=========================================="
echo ""

# Step 1: Copy service files to systemd directory
echo "1. Installing service files..."
sudo cp $WORKSPACE/systemd/auto-trade-api.service /etc/systemd/system/
sudo cp $WORKSPACE/systemd/auto-trade-worker.service /etc/systemd/system/
echo "✅ Service files installed"
echo ""

# Step 2: Reload systemd daemon
echo "2. Reloading systemd daemon..."
sudo systemctl daemon-reload
echo "✅ Daemon reloaded"
echo ""

# Step 3: Enable services (auto-start on boot)
echo "3. Enabling services..."
sudo systemctl enable auto-trade-api.service
sudo systemctl enable auto-trade-worker.service
echo "✅ Services enabled"
echo ""

# Step 4: Check status
echo "4. Checking service status..."
echo ""
echo "API Service:"
sudo systemctl status auto-trade-api.service --no-pager -l | head -15
echo ""
echo "Worker Service:"
sudo systemctl status auto-trade-worker.service --no-pager -l | head -15
echo ""

# Step 5: Start services (optional - comment out if you want to start manually)
echo "5. Starting services..."
sudo systemctl start auto-trade-api.service
sudo systemctl start auto-trade-worker.service
echo "✅ Services started"
echo ""

# Step 6: Verify they're running
echo "6. Verifying services are running..."
sleep 3
sudo systemctl is-active auto-trade-api.service
sudo systemctl is-active auto-trade-worker.service
echo ""

echo "=========================================="
echo "  Installation Complete! ✅"
echo "=========================================="
echo ""
echo "Quick Commands:"
echo "  Status:   sudo systemctl status auto-trade-api auto-trade-worker"
echo "  Logs:     journalctl -u auto-trade-api -f"
echo "  Stop:     sudo systemctl stop auto-trade-api auto-trade-worker"
echo "  Restart:  sudo systemctl restart auto-trade-api auto-trade-worker"
echo ""
