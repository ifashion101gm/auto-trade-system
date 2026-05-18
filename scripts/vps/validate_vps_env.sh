#!/bin/bash
# Validate VPS environment
# Purpose: Verify VPS environment meets requirements before deployment

set -euo pipefail

echo "🔍 Validating VPS environment..."
echo ""

ERRORS=0
WARNINGS=0

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not installed"
    ERRORS=$((ERRORS + 1))
else
    echo "✅ Docker: $(docker --version)"
fi

# Check Docker Compose
if ! command -v docker compose &> /dev/null; then
    echo "❌ Docker Compose not installed"
    ERRORS=$((ERRORS + 1))
else
    echo "✅ Docker Compose: $(docker compose version)"
fi

# Check Tailscale
if ! command -v tailscale &> /dev/null; then
    echo "❌ Tailscale not installed"
    ERRORS=$((ERRORS + 1))
else
    if tailscale status --json 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['Self']['Online'])" 2>/dev/null | grep -q "true"; then
        TAILSCALE_IP=$(tailscale ip -4)
        echo "✅ Tailscale: Connected (IP: $TAILSCALE_IP)"
    else
        echo "❌ Tailscale: Not connected"
        ERRORS=$((ERRORS + 1))
    fi
fi

# Check Node.js (for Claude Code)
if ! command -v node &> /dev/null; then
    echo "⚠️  Node.js not installed (required for Claude Code CLI)"
    WARNINGS=$((WARNINGS + 1))
else
    echo "✅ Node.js: $(node --version)"
fi

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "⚠️  Python3 not installed"
    WARNINGS=$((WARNINGS + 1))
else
    echo "✅ Python3: $(python3 --version)"
fi

# Check firewall
if sudo ufw status 2>/dev/null | grep -q "Status: active"; then
    echo "✅ Firewall: Active"
else
    echo "⚠️  Firewall: Inactive (recommended to enable)"
    WARNINGS=$((WARNINGS + 1))
fi

# Check available disk space
DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -gt 80 ]; then
    echo "⚠️  Disk usage high: ${DISK_USAGE}%"
    WARNINGS=$((WARNINGS + 1))
else
    echo "✅ Disk usage: ${DISK_USAGE}%"
fi

# Check available memory
MEM_AVAILABLE=$(free -m | awk 'NR==2{printf "%.0f", $7*100/$2}')
if [ "$MEM_AVAILABLE" -lt 20 ]; then
    echo "⚠️  Low available memory: ${MEM_AVAILABLE}%"
    WARNINGS=$((WARNINGS + 1))
else
    echo "✅ Available memory: ${MEM_AVAILABLE}%"
fi

echo ""
echo "============================================================"
echo "Summary"
echo "============================================================"

if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo "✅ All checks passed! Ready for deployment."
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo "⚠️  Found $WARNINGS warning(s). Review above."
    echo "   You can proceed with deployment, but consider fixing warnings."
    exit 0
else
    echo "❌ Found $ERRORS error(s). Fix before deploying."
    exit 1
fi
