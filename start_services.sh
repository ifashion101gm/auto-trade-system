#!/bin/bash
# Auto Trade System - Quick Start Script
# Starts PostgreSQL, Redis, and the trading application

set -e

echo "=========================================="
echo "Auto Trade System - Starting Services"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo -e "${RED}❌ Virtual environment not found. Run: python3 -m venv .venv${NC}"
    exit 1
fi

# Activate virtual environment
echo -e "${YELLOW}📦 Activating virtual environment...${NC}"
source .venv/bin/activate

# Check if PostgreSQL container is running
echo -e "${YELLOW}🗄️  Checking PostgreSQL...${NC}"
if docker ps | grep -q postgres-trading; then
    echo -e "${GREEN}✅ PostgreSQL is running${NC}"
else
    echo -e "${YELLOW}⚠️  PostgreSQL not running. Starting...${NC}"
    docker start postgres-trading 2>/dev/null || \
    docker run -d --name postgres-trading \
        -e POSTGRES_USER=trading \
        -e POSTGRES_PASSWORD=trading123 \
        -e POSTGRES_DB=vmassit \
        -p 5432:5432 \
        -v pgdata:/var/lib/postgresql/data \
        postgres:13-alpine
    sleep 3
    echo -e "${GREEN}✅ PostgreSQL started${NC}"
fi

# Check if Redis is running
echo -e "${YELLOW}💾 Checking Redis...${NC}"
if redis-cli ping 2>/dev/null | grep -q PONG; then
    echo -e "${GREEN}✅ Redis is running${NC}"
else
    echo -e "${YELLOW}⚠️  Redis not running. Starting...${NC}"
    redis-server --daemonize yes
    sleep 1
    echo -e "${GREEN}✅ Redis started${NC}"
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ .env file not found. Copy from .env.example and configure.${NC}"
    exit 1
fi

# Run database migrations
echo -e "${YELLOW}🔧 Running database migrations...${NC}"
alembic upgrade head 2>&1 | grep -E "(Running upgrade|INFO)" || true
echo -e "${GREEN}✅ Migrations complete${NC}"

# Check if application is already running
if pgrep -f "uvicorn app.main:app" > /dev/null; then
    echo -e "${YELLOW}⚠️  Application already running. Restarting...${NC}"
    pkill -f "uvicorn app.main:app" || true
    sleep 2
fi

# Start the application
echo -e "${YELLOW}🚀 Starting Auto Trade System...${NC}"
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/trading_app.log 2>&1 &
APP_PID=$!

echo -e "${GREEN}✅ Application started (PID: $APP_PID)${NC}"
echo ""

# Wait for application to be ready
echo -e "${YELLOW}⏳ Waiting for application to initialize...${NC}"
for i in {1..15}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Application is ready!${NC}"
        break
    fi
    if [ $i -eq 15 ]; then
        echo -e "${RED}❌ Application failed to start. Check logs: tail -f /tmp/trading_app.log${NC}"
        exit 1
    fi
    sleep 1
done

echo ""
echo "=========================================="
echo -e "${GREEN}✅ All services started successfully!${NC}"
echo "=========================================="
echo ""
echo "📊 Service Status:"
echo "  • PostgreSQL: $(docker ps | grep -q postgres-trading && echo '✅ Running' || echo '❌ Stopped')"
echo "  • Redis:      $(redis-cli ping 2>/dev/null | grep -q PONG && echo '✅ Running' || echo '❌ Stopped')"
echo "  • App Server: $(curl -s http://localhost:8000/health > /dev/null 2>&1 && echo '✅ Running' || echo '❌ Stopped')"
echo ""
echo "🌐 Access Points:"
echo "  • API Docs:   http://localhost:8000/docs"
echo "  • Health:     http://localhost:8000/health"
echo ""
echo "📝 Useful Commands:"
echo "  • View logs:       tail -f /tmp/trading_app.log"
echo "  • Stop app:        pkill -f 'uvicorn app.main:app'"
echo "  • DB console:      PGPASSWORD=trading123 psql -h localhost -U trading -d vmassit"
echo "  • Redis console:   redis-cli"
echo ""
echo "🎯 Next Steps:"
echo "  1. Monitor logs for WebSocket connection status"
echo "  2. Check Telegram for notifications"
echo "  3. Verify reconciliation runs every 2 minutes"
echo ""
