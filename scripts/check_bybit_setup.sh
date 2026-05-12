#!/bin/bash
# Quick validation script to check Bybit setup status
# Run this after updating API keys to verify everything works

echo "========================================================================"
echo "  BYBIT SETUP VALIDATION - QUICK CHECK"
echo "========================================================================"
echo ""

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ ERROR: .env file not found"
    echo "   Please create .env file with your API credentials"
    exit 1
fi

# Extract API key (masked)
API_KEY=$(grep BYBIT_API_KEY .env | cut -d'=' -f2 | head -c 8)
echo "📋 Configuration Check:"
echo "   • API Key: ${API_KEY}..."
echo "   • Config file: ✅ Found"
echo ""

# Activate virtual environment
if [ -d ".venv" ]; then
    source .venv/bin/activate
    echo "✅ Virtual environment activated"
else
    echo "❌ Virtual environment not found"
    exit 1
fi

echo ""
echo "Running diagnostic check..."
echo ""

# Run diagnostic script
PYTHONPATH=/home/admin/.openclaw/workspace/auto-trade-system \
    python scripts/diagnose_bybit_account.py 2>&1 | grep -E "TEST|✅|❌|USDT Total|USDT Wallet|Results" | head -20

echo ""
echo "========================================================================"
echo "  INTERPRETING RESULTS"
echo "========================================================================"
echo ""
echo "If you see:"
echo "  • USDT Total: \$100,008,018.00 → ✅ Demo account working!"
echo "  • USDT Total: \$0.00             → ❌ Need new API keys from demo mode"
echo ""
echo "Next steps:"
echo "  1. If balance is \$0, follow BYBIT_DEMO_ACCOUNT_SETUP.md"
echo "  2. Generate new API keys while in demo mode"
echo "  3. Update .env file with new credentials"
echo "  4. Run this script again"
echo ""
echo "Full documentation:"
echo "  • Setup Guide: BYBIT_DEMO_ACCOUNT_SETUP.md"
echo "  • Status Summary: BYBIT_STATUS_SUMMARY.md"
echo "  • Validation Report: BYBIT_VALIDATION_FINAL_REPORT.md"
echo ""
