#!/bin/bash
#
# Verify Enterprise v3.0.0 Systemd Services
# Run this after installation to confirm everything is working
#

WORKSPACE="/home/admin/.openclaw/workspace/auto-trade-system"

echo "=========================================="
echo "  Service Verification Checklist"
echo "=========================================="
echo ""

# Check 1: Service files installed
echo "✓ Check 1: Service files installed"
if [ -f /etc/systemd/system/auto-trade-api.service ] && [ -f /etc/systemd/system/auto-trade-worker.service ]; then
    echo "  ✅ Service files found in /etc/systemd/system/"
else
    echo "  ❌ Service files NOT found"
    echo "     Run: sudo ./install_systemd_services.sh"
fi
echo ""

# Check 2: Services enabled
echo "✓ Check 2: Services enabled for auto-start"
API_ENABLED=$(sudo systemctl is-enabled auto-trade-api.service 2>/dev/null || echo "not-found")
WORKER_ENABLED=$(sudo systemctl is-enabled auto-trade-worker.service 2>/dev/null || echo "not-found")

if [ "$API_ENABLED" == "enabled" ]; then
    echo "  ✅ API service enabled"
else
    echo "  ❌ API service not enabled (current: $API_ENABLED)"
fi

if [ "$WORKER_ENABLED" == "enabled" ]; then
    echo "  ✅ Worker service enabled"
else
    echo "  ❌ Worker service not enabled (current: $WORKER_ENABLED)"
fi
echo ""

# Check 3: Services active
echo "✓ Check 3: Services currently running"
API_STATUS=$(sudo systemctl is-active auto-trade-api.service 2>/dev/null || echo "inactive")
WORKER_STATUS=$(sudo systemctl is-active auto-trade-worker.service 2>/dev/null || echo "inactive")

if [ "$API_STATUS" == "active" ]; then
    echo "  ✅ API service is active"
else
    echo "  ⚠️  API service status: $API_STATUS"
fi

if [ "$WORKER_STATUS" == "active" ]; then
    echo "  ✅ Worker service is active"
else
    echo "  ⚠️  Worker service status: $WORKER_STATUS"
fi
echo ""

# Check 4: API endpoints responding
echo "✓ Check 4: API endpoints responding"
sleep 2

# Test root endpoint
ROOT_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/ 2>/dev/null || echo "000")
if [ "$ROOT_RESPONSE" == "200" ]; then
    echo "  ✅ Root endpoint (HTTP $ROOT_RESPONSE)"
else
    echo "  ❌ Root endpoint (HTTP $ROOT_RESPONSE)"
fi

# Test health endpoint
HEALTH_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health/deep 2>/dev/null || echo "000")
if [ "$HEALTH_RESPONSE" == "200" ]; then
    echo "  ✅ Health endpoint (HTTP $HEALTH_RESPONSE)"
else
    echo "  ❌ Health endpoint (HTTP $HEALTH_RESPONSE)"
fi

# Test admin endpoint
ADMIN_KEY=$(grep ADMIN_API_KEY $WORKSPACE/.env 2>/dev/null | head -1 | cut -d= -f2)
if [ -n "$ADMIN_KEY" ]; then
    ADMIN_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" -H "x-api-key: $ADMIN_KEY" http://localhost:8000/admin/state 2>/dev/null || echo "000")
    if [ "$ADMIN_RESPONSE" == "200" ]; then
        echo "  ✅ Admin endpoint (HTTP $ADMIN_RESPONSE)"
    else
        echo "  ❌ Admin endpoint (HTTP $ADMIN_RESPONSE)"
    fi
else
    echo "  ⚠️  ADMIN_API_KEY not found in .env"
fi
echo ""

# Check 5: Show current status
echo "✓ Check 5: Current system status"
if [ "$HEALTH_RESPONSE" == "200" ]; then
    echo "  System Info:"
    curl -s http://localhost:8000/ | python3 -m json.tool 2>/dev/null | grep -E "(version|name)" || true
    echo ""
    echo "  Health Status:"
    curl -s http://localhost:8000/health/deep | python3 -m json.tool 2>/dev/null | grep -E "(status|session|news_safe)" || true
fi
echo ""

# Check 6: Recent logs
echo "✓ Check 6: Recent service logs (last 5 entries)"
echo ""
echo "  API Service Logs:"
sudo journalctl -u auto-trade-api.service -n 5 --no-pager 2>/dev/null | tail -5 || echo "    No logs available"
echo ""
echo "  Worker Service Logs:"
sudo journalctl -u auto-trade-worker.service -n 5 --no-pager 2>/dev/null | tail -5 || echo "    No logs available"
echo ""

# Summary
echo "=========================================="
echo "  Summary"
echo "=========================================="
echo ""

if [ "$API_STATUS" == "active" ] && [ "$WORKER_STATUS" == "active" ] && [ "$HEALTH_RESPONSE" == "200" ]; then
    echo "✅ ALL CHECKS PASSED"
    echo ""
    echo "Your Enterprise v3.0.0 system is fully operational!"
    echo ""
    echo "Quick Commands:"
    echo "  • Monitor: journalctl -u auto-trade-api -u auto-trade-worker -f"
    echo "  • Restart: sudo systemctl restart auto-trade-api auto-trade-worker"
    echo "  • Status:  sudo systemctl status auto-trade-api auto-trade-worker"
elif [ "$API_STATUS" == "active" ]; then
    echo "⚠️  PARTIAL SUCCESS"
    echo ""
    echo "API service is running, but there may be issues with:"
    [ "$WORKER_STATUS" != "active" ] && echo "  • Worker service (status: $WORKER_STATUS)"
    [ "$HEALTH_RESPONSE" != "200" ] && echo "  • Health endpoint (HTTP $HEALTH_RESPONSE)"
    echo ""
    echo "Check logs: journalctl -u auto-trade-api -u auto-trade-worker -n 50"
else
    echo "❌ ISSUES DETECTED"
    echo ""
    echo "Services are not running properly. Troubleshooting:"
    echo "  1. Check logs: journalctl -u auto-trade-api -n 50"
    echo "  2. Try restart: sudo systemctl restart auto-trade-api auto-trade-worker"
    echo "  3. Check config: cat /etc/systemd/system/auto-trade-api.service"
fi
echo ""
