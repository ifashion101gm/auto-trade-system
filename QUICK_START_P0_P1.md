# 🚀 Quick Start Guide - New P0/P1 Features

**New Features:** Containerized services, Makefile automation, comprehensive test suite

---

## 🐳 Docker Services (NEW!)

### Start All Services
```bash
# Infrastructure + Application
make docker-up

# Or manually
docker-compose up -d
```

### Check Service Health
```bash
make health
```

**Expected Output:**
```
🏥 Checking service health...

PostgreSQL:
✅ Healthy

Redis:
✅ Healthy

Trading Bot API:
✅ Healthy

Prometheus:
✅ Healthy

Grafana:
✅ Healthy
```

### View Logs
```bash
# All services
make docker-logs

# API only
make docker-logs-api

# Worker only
make docker-logs-worker
```

### Stop Services
```bash
make docker-down
```

---

## 🛠️ Makefile Commands (NEW!)

### First-Time Setup
```bash
# 1. Setup environment (Python venv + dependencies)
make setup

# 2. Edit .env with your API keys
nano .env

# 3. Start development environment
make dev
```

### Daily Development
```bash
# Start everything (infra + app)
make dev

# Run tests
make test

# Format code
make format

# Check code quality
make lint
```

### Testing
```bash
# All tests
make test

# Unit tests only
make test-unit

# Integration tests only
make test-integration

# Chaos/resilience tests
make test-chaos

# With coverage report
make coverage
```

### Deployment
```bash
# Deploy to production (systemd)
make deploy

# Start/stop/restart production
make deploy-start
make deploy-stop
make deploy-restart

# Check status
make deploy-status
```

### Database Operations
```bash
# Run migrations
make db-migrate

# Backup database
make db-backup

# Reset database (WARNING: deletes all data!)
make db-reset
```

### Cleanup
```bash
# Clean temporary files
make clean

# Clean everything (including venv)
make clean-all

# Clear logs
make logs-clear
```

### Help
```bash
# Show all commands
make help
```

---

## 🧪 Running Tests

### Unit Tests (Fast, No Database Required)
```bash
# Execution service tests (15+ tests)
pytest tests/unit/test_execution_service.py -v

# Risk engine tests (12+ tests)
pytest tests/unit/test_risk_engine.py -v

# All unit tests
make test-unit
```

**Expected Output:**
```
tests/unit/test_execution_service.py::TestExecutionRequest::test_create_basic_request PASSED
tests/unit/test_execution_service.py::TestExecutionServiceValidation::test_reject_invalid_side PASSED
...
======================== 27 passed in 2.34s ========================
```

---

### Integration Tests (Requires Test Database)
```bash
# Database concurrency tests (7 tests)
pytest tests/integration/test_database_concurrency.py -v

# WebSocket reconnection tests (15+ tests)
pytest tests/integration/test_websocket_reconnection.py -v

# All integration tests
make test-integration
```

**Setup Test Database:**
```bash
# Create test database
docker exec -it trading-postgres psql -U trading -c "CREATE DATABASE vmassit_test;"

# Run migrations on test database
DATABASE_URL=postgresql+asyncpg://trading:testpassword@localhost:5432/vmassit_test \
  python -m alembic upgrade head
```

---

## 🔍 Troubleshooting

### Docker Services Won't Start

**Problem:** PostgreSQL or Redis fails to start

**Solution:**
```bash
# Check logs
docker-compose logs postgres
docker-compose logs redis

# Common fix: Remove old volumes
docker-compose down -v
docker-compose up -d
```

---

### Health Checks Failing

**Problem:** `make health` shows services unhealthy

**Solution:**
```bash
# Wait 60 seconds for services to initialize
sleep 60

# Check individual service
docker inspect trading-bot-api | grep -A 10 Health

# Restart unhealthy service
docker-compose restart trading-bot
```

---

### Tests Failing

**Problem:** Unit tests fail with import errors

**Solution:**
```bash
# Ensure virtual environment is activated
source .venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt

# Run tests again
make test
```

---

### Database Connection Errors

**Problem:** "Connection refused" when running tests

**Solution:**
```bash
# Verify PostgreSQL is running
docker ps | grep postgres

# Check connection string
echo $DATABASE_URL

# Test connection
docker exec -it trading-postgres pg_isready -U trading
```

---

### WebSocket Connection Issues

**Problem:** WebSocket tests fail to connect

**Solution:**
```bash
# Check if exchange API is accessible
curl https://api-testnet.bybit.com

# Verify API keys in .env
grep BYBIT_API .env

# Check network connectivity
ping api-testnet.bybit.com
```

---

## 📊 Monitoring

### Prometheus Metrics
```bash
# Open Prometheus UI
open http://localhost:9090

# Query trading metrics
bot_trading_enabled
background_tasks_running
http_requests_total
```

### Grafana Dashboards
```bash
# Open Grafana (default password: admin/admin)
open http://localhost:3000

# Import dashboards from monitoring/grafana/dashboards/
```

### Application Logs
```bash
# Tail logs
make logs

# Search for errors
grep ERROR logs/app_*.log

# View JSON structured logs
make logs-json
```

---

## 🎯 Common Workflows

### Workflow 1: Start Development Environment
```bash
# 1. Clone repo (if not done)
git clone <repo-url>
cd auto-trade-system

# 2. Setup environment
make setup

# 3. Configure API keys
nano .env

# 4. Start everything
make dev

# 5. Open dashboard
open http://localhost:8000/docs
```

---

### Workflow 2: Run Tests Before Commit
```bash
# 1. Format code
make format

# 2. Run linters
make lint

# 3. Run type checker
make check-types

# 4. Run all tests
make test

# 5. Check coverage
make coverage

# 6. Commit if all pass
git add .
git commit -m "feat: add new feature"
```

---

### Workflow 3: Deploy to Production
```bash
# 1. Run tests
make test

# 2. Build Docker images
make docker-build

# 3. Deploy systemd services
make deploy

# 4. Check status
make deploy-status

# 5. Monitor logs
journalctl -u auto-trade-api -f
```

---

### Workflow 4: Debug Production Issue
```bash
# 1. Check service status
make deploy-status

# 2. View recent logs
journalctl -u auto-trade-api --since "1 hour ago"

# 3. Check health
curl http://localhost:8000/api/v1/health

# 4. View metrics
curl http://localhost:8000/metrics

# 5. Restart if needed
make deploy-restart
```

---

## 📚 Additional Resources

- **Full Documentation:** [P0_P1_IMPLEMENTATION_COMPLETE.md](./P0_P1_IMPLEMENTATION_COMPLETE.md)
- **Audit Report:** [INFRASTRUCTURE_AND_TESTING_AUDIT_REPORT.md](./INFRASTRUCTURE_AND_TESTING_AUDIT_REPORT.md)
- **Self-Healing Architecture:** [docs/SELF_HEALING_ARCHITECTURE.md](./docs/SELF_HEALING_ARCHITECTURE.md)
- **Docker Compose Reference:** [docker-compose.yml](./docker-compose.yml)

---

## 💡 Pro Tips

1. **Use `make help` frequently** - Discover all available commands
2. **Run `make test` before every commit** - Catch bugs early
3. **Monitor with `make health`** - Check service status quickly
4. **Use `make format` + `make lint`** - Keep code clean
5. **Backup before `make db-reset`** - Don't lose data!
6. **Check `make stats`** - Track project growth
7. **Use Docker for consistency** - Same environment everywhere
8. **Read logs with `make logs`** - Debug faster

---

**Happy Coding! 🎉**
