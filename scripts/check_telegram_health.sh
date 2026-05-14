#!/bin/bash
# Telegram Notification System Health Check
# Verifies Telegram bot connectivity and configuration

echo "=========================================="
echo "Telegram Notification System - Health Check"
echo "=========================================="
echo ""

# Load environment variables
source /home/admin/.openclaw/workspace/auto-trade-system/.venv/bin/activate
cd /home/admin/.openclaw/workspace/auto-trade-system

# 1. Check configuration
echo "1️⃣  Configuration Check:"
BOT_TOKEN=$(grep "^TELEGRAM_BOT_TOKEN=" .env | cut -d'=' -f2)
CHAT_ID=$(grep "^TELEGRAM_CHAT_ID=" .env | cut -d'=' -f2)

if [ -n "$BOT_TOKEN" ] && [ "$BOT_TOKEN" != "your-telegram-bot-token-here" ]; then
    echo "   ✅ Bot token configured"
    TOKEN_MASKED="${BOT_TOKEN:0:8}...${BOT_TOKEN: -4}"
    echo "   Token: $TOKEN_MASKED"
else
    echo "   ❌ Bot token not configured or invalid"
fi

if [ -n "$CHAT_ID" ]; then
    echo "   ✅ Chat ID configured: $CHAT_ID"
else
    echo "   ❌ Chat ID not configured"
fi
echo ""

# 2. Test bot connectivity
echo "2️⃣  Bot Connectivity Test:"
if [ -n "$BOT_TOKEN" ] && [ "$BOT_TOKEN" != "your-telegram-bot-token-here" ]; then
    RESPONSE=$(curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getMe" 2>&1)
    
    if echo "$RESPONSE" | grep -q '"ok":true'; then
        BOT_NAME=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['result']['first_name'])" 2>/dev/null)
        echo "   ✅ Bot is reachable"
        echo "   Bot Name: $BOT_NAME"
        
        # Check if chat exists
        CHAT_RESPONSE=$(curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getChat?chat_id=${CHAT_ID}" 2>&1)
        if echo "$CHAT_RESPONSE" | grep -q '"ok":true'; then
            CHAT_TYPE=$(echo "$CHAT_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['result']['type'])" 2>/dev/null)
            echo "   ✅ Chat is valid (Type: $CHAT_TYPE)"
        else
            echo "   ⚠️  Chat ID may be invalid or bot not added to chat"
            echo "   Response: $CHAT_RESPONSE"
        fi
    else
        echo "   ❌ Bot is NOT reachable"
        echo "   Response: $RESPONSE"
    fi
else
    echo "   ⏭️  Skipped (bot token not configured)"
fi
echo ""

# 3. Check recent Telegram logs
echo "3️⃣  Recent Telegram Activity:"
LOG_FILE="/home/admin/.openclaw/workspace/auto-trade-system/logs/all_$(date +%Y-%m-%d).log"

if [ -f "$LOG_FILE" ]; then
    TELEGRAM_COUNT=$(grep -c "Telegram" "$LOG_FILE" 2>/dev/null || echo "0")
    echo "   Total Telegram log entries today: $TELEGRAM_COUNT"
    
    echo ""
    echo "   Last 5 Telegram events:"
    grep "Telegram" "$LOG_FILE" | tail -5 | while read line; do
        TIMESTAMP=$(echo "$line" | grep -oP '^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}')
        MESSAGE=$(echo "$line" | grep -oP '(?<=Telegram: ).*')
        echo "   [$TIMESTAMP] $MESSAGE"
    done
else
    echo "   ⚠️  Log file not found: $LOG_FILE"
fi
echo ""

# 4. Check for Telegram errors
echo "4️⃣  Error Check:"
ERROR_LOG="/home/admin/.openclaw/workspace/auto-trade-system/logs/error_$(date +%Y-%m-%d).log"

if [ -f "$ERROR_LOG" ]; then
    TELEGRAM_ERRORS=$(grep -i "telegram" "$ERROR_LOG" 2>/dev/null | wc -l)
    if [ "$TELEGRAM_ERRORS" -eq 0 ]; then
        echo "   ✅ No Telegram errors today"
    else
        echo "   ❌ Found $TELEGRAM_ERRORS Telegram error(s):"
        grep -i "telegram" "$ERROR_LOG" | tail -3 | while read line; do
            echo "      $line"
        done
    fi
else
    echo "   ✅ No error log file (or no errors recorded)"
fi
echo ""

# 5. Test notification (optional)
echo "5️⃣  Test Notification:"
read -p "   Send test notification? (y/N): " SEND_TEST
if [[ "$SEND_TEST" =~ ^[Yy]$ ]]; then
    TEST_MESSAGE="🧪 <b>Test Notification</b>\n\nAuto Trade System validation cycle is running.\nTime: $(date '+%Y-%m-%d %H:%M:%S UTC')\nStatus: ✅ All systems operational"
    
    RESPONSE=$(curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
        -d "chat_id=$CHAT_ID" \
        -d "text=$TEST_MESSAGE" \
        -d "parse_mode=HTML" 2>&1)
    
    if echo "$RESPONSE" | grep -q '"ok":true'; then
        echo "   ✅ Test notification sent successfully!"
    else
        echo "   ❌ Failed to send test notification"
        echo "   Response: $RESPONSE"
    fi
else
    echo "   ⏭️  Skipped"
fi
echo ""

echo "=========================================="
echo "Health check complete!"
echo "=========================================="
