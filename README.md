# Auto Trade System - Self-Healing Trading Infrastructure

Production-ready, self-healing automated trading system with AI-powered decision making, Bybit integration (pybit SDK), and resilient closed-loop architecture.

**Python Version**: 3.11+ required  
**Status**: ✅ Production Ready (v2.0.0 - Self-Healing Edition)  
**Active Exchange**: Bybit (Demo Trading via pybit SDK)  
**Execution Mode**: semi-auto (hybrid threshold: $100)

## 🎯 Overview

This repository contains a **self-healing automated trading infrastructure** capable of 24/7 autonomous operation with minimal human oversight. The system features a resilient closed-loop lifecycle (Signal → Execution → Verification → Monitoring → Recovery → Reconciliation) with automatic failure detection and repair.

### Key Capabilities
- 🤖 **6 Specialized AI Agents** with isolated responsibilities
- 🛡️ **Duplicate Order Protection** preventing double execution
- 🔍 **AI Anomaly Detection** identifying unusual patterns
- ♻️ **Automatic Recovery** from runtime failures
- 📊 **Continuous Reconciliation** ensuring data integrity
- 🌐 **Multi-Exchange Support** (Bybit primary, Binance/MEXC available)

## ✨ Features

### 1. Database Migration System (Alembic)
- Version-controlled schema management with SQLAlchemy ORM models
- Safe upgrade/downgrade paths  
- CLI tool for easy operations
- PostgreSQL database support with connection pooling and async operations

### 2. Automated Backup/Restore System
- Compressed daily backups (gzip ~90% space savings)
- Integrity verification after backup
- Automatic rotation (configurable retention)
- One-command restore with safety checks
- Systemd timer for automated scheduling

### 3. Learning API Endpoints
- REST API for monitoring self-learning systems
- Real-time insights and parameter tracking
- Manual learning cycle triggering
- Performance metrics and history

### 4. Data Export/Import Utilities
- Export trades, performance, strategies to CSV/JSON
- Filterable and paginated results
- Complete data archiving

### 5. Centralized Configuration
- Type-safe environment variable management via Pydantic Settings
- Support for `.env` files and production secrets

### 6. Multi-Exchange Trading Integration
- **Bybit Demo Trading** (Primary) using official pybit SDK
  - Connects to api-demo.bybit.com for virtual fund trading
  - Full V5 API compliance with proper error handling
  - Supports linear perpetual swaps (BTCUSDT, ETHUSDT, XAUUSDT)
- **Binance Testnet** for paper trading validation
- **MEXC** integration available (archived documentation)
- CCXT-based exchange abstraction layer for unified interface

### 7. Real-Time Monitoring Stack
- Prometheus metrics collection
- Grafana dashboards for visualization
- WebSocket-based real-time position updates
- Telegram notifications for trade events

### 8. Enhanced Production Monitoring (NEW)
- **Order State Tracking**: Real-time lifecycle monitoring with ORDER_STATE_CHANGED events
- **Risk Violation Alerts**: Immediate notifications for HIGH/CRITICAL risk breaches
- **Reconciliation Monitoring**: Automated mismatch detection and repair alerts
- **Advanced Query Tools**: Pre-built scripts for risk, recovery, and execution analysis
- **Event Store Integration**: Complete audit trail for all critical operations

### 9. Self-Healing Architecture (v2.0 - LATEST)
- **6 Specialized Agents**: Signal, Execution, Verification, Monitoring, Recovery, Reconciliation
- **Closed-Loop Lifecycle**: Signal → Execution → Verification → Monitoring → Recovery → Reconciliation
- **Duplicate Order Protection**: SHA256 signal hashing prevents double execution
- **AI Anomaly Detection**: Statistical analysis of latency, failures, slippage, overtrading
- **Automatic Recovery**: Circuit breaker cooldown, API reconnection, state reset
- **Continuous Reconciliation**: Exchange-DB sync every 60 seconds with auto-repair
- **Zero Manual Intervention**: Transient errors handled automatically
- **Full Audit Trail**: All state transitions and recovery actions logged

## 🚀 Quick Start

```bash
# Clone and setup
git clone <your-repo-url>
cd auto-trade-system

# Ensure Python 3.11+ is installed (available via Linuxbrew at /home/linuxbrew/.linuxbrew/bin/python3.11)
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run migrations
python migrate.py upgrade

# Create backup
./scripts/backup_database.sh

# Enable automated backups
sudo systemctl enable --now vmassit-backup.timer
```

### Production Monitoring Setup (NEW)

```bash
# Test enhanced notifications
python scripts/test_enhanced_notifications.py

# Run monitoring queries
python scripts/production_monitoring_queries.py

# Deploy all enhancements
./deploy_production_enhancements.sh

# View documentation
cat PRODUCTION_ENHANCED_MONITORING.md
cat QUICK_REFERENCE_PRODUCTION_MONITORING.md
```

## 📚 Installation & Technology References

This section provides direct links to official documentation for all core technologies used in the Auto Trade System.

### Core Technologies

#### 1. Python Async Programming
The system leverages Python's `asyncio` library for high-performance, non-blocking I/O operations essential for real-time trading.

- **Python Version**: 3.11+ required (currently using Python 3.11.15)
- **Official Documentation**: [Python asyncio](https://docs.python.org/3/library/asyncio.html)
- **Key Concepts**: Event loops, coroutines, async/await syntax, concurrent tasks
- **Used In**: Database operations, API calls, WebSocket connections, exchange communications

#### 2. FastAPI Framework
FastAPI provides the REST API layer with automatic OpenAPI documentation, async support, and type safety via Pydantic.

- **Official Documentation**: [FastAPI Docs](https://fastapi.tiangolo.com/)
- **Tutorial**: [FastAPI Tutorial](https://fastapi.tiangolo.com/tutorial/)
- **Key Features**: Automatic API docs (`/docs`), dependency injection, async endpoint support
- **Version**: 0.136.1 (see `requirements.txt`)

#### 3. PostgreSQL Database
PostgreSQL serves as the primary database for persistent storage of trades, positions, and system state.

- **Official Documentation**: [PostgreSQL Docs](https://www.postgresql.org/docs/)
- **Latest Version**: [PostgreSQL 15 Documentation](https://www.postgresql.org/docs/15/)
- **Async Driver**: [asyncpg](https://magicstack.github.io/asyncpg/current/) (used via SQLAlchemy)
- **ORM**: [SQLAlchemy 2.0](https://docs.sqlalchemy.org/en/20/)
- **Migrations**: [Alembic](https://alembic.sqlalchemy.org/)
- **Connection Pooling**: Configured in `app/config.py` (pool_size, max_overflow, timeout)

#### 4. Redis Cache & Event Bus
Redis provides caching, pub/sub event distribution, and session management capabilities.

- **Official Documentation**: [Redis Docs](https://redis.io/documentation)
- **Commands Reference**: [Redis Commands](https://redis.io/commands/)
- **Python Client**: [redis-py](https://redis.readthedocs.io/en/stable/) (version 7.4.0)
- **Use Cases**: 
  - Three-tier caching system
  - Real-time event broadcasting via pub/sub
  - Position synchronization coordination
- **Docker Image**: `redis:7-alpine`

#### 5. Docker Containerization
Docker Compose orchestrates the entire infrastructure stack including databases, monitoring, and application services.

- **Official Documentation**: [Docker Docs](https://docs.docker.com/)
- **Docker Compose**: [Compose Specification](https://docs.docker.com/compose/)
- **Quick Start**:
  ```bash
  # Start all infrastructure services
  docker-compose up -d
  
  # View logs
  docker-compose logs -f
  
  # Stop services
  docker-compose down
  ```
- **Services Included**:
  - PostgreSQL 15 (database)
  - Redis 7 (cache & events)
  - Prometheus (metrics collection)
  - Grafana (visualization dashboards)

### Additional Technology Stack

#### Exchange Integration
- **Bybit pybit SDK**: [pybit Documentation](https://bybit-exchange.github.io/pybit/) (official Bybit SDK)
  - Required for Demo Trading support (CCXT does NOT support demo mode)
  - Full V5 API compliance with proper error handling
  - Used in: `app/infra/bybit_client.py`, `app/infra/pybit_demo_client.py`
- **CCXT Library**: [CCXT Documentation](https://docs.ccxt.com/) (version 4.5.18)
  - Unified crypto exchange API abstraction for testnet/mainnet
  - Supports Binance, MEXC, and other exchanges
  - Not used for Bybit Demo Trading (pybit required)
- **MEXC Futures API**: [MEXC API Docs](https://mexcdevelop.github.io/apidocs/contract_v1_en/)
- **Binance API**: [Binance API Docs](https://binance-docs.github.io/apidocs/)

#### AI/LLM Integration
- **OpenRouter**: [OpenRouter API](https://openrouter.ai/docs) (unified LLM gateway)
- **OpenAI**: [OpenAI API](https://platform.openai.com/docs/) (version 2.36.0)
- **Anthropic Claude**: [Anthropic API](https://docs.anthropic.com/) (version 0.100.0)
- **Google Gemini**: [Google AI](https://ai.google.dev/) (version 0.8.6)

#### Monitoring & Observability
- **Prometheus**: [Prometheus Docs](https://prometheus.io/docs/)
  - Metrics collection and alerting
  - Configuration: `monitoring/prometheus.yml`
- **Grafana**: [Grafana Docs](https://grafana.com/docs/)
  - Dashboard visualization
  - Pre-configured dashboards in `monitoring/grafana/dashboards/`
- **Prometheus Client**: [Python Client](https://prometheus.github.io/client_python/) (version 0.19.0+)

#### WebSockets & Real-Time Communication
- **websockets Library**: [websockets Docs](https://websockets.readthedocs.io/) (version 12.0+)
  - Real-time position updates from exchanges
  - Event-driven architecture
  - Automatic reconnection with exponential backoff

#### Configuration Management
- **Pydantic Settings**: [Pydantic Settings Docs](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) (version 2.12.0)
  - Type-safe environment variable management
  - `.env` file support
  - Validation and defaults

#### Background Tasks
- **Dramatiq**: [Dramatiq Docs](https://dramatiq.io/) (version 2.1.0)
  - Background task processing
  - Redis-based message broker
  - Reliable job execution

### Development Tools

#### Testing & Validation
- **pytest**: Standard Python testing framework
- **Test Scripts**: Located in `scripts/validate_*.py`
- **Integration Tests**: End-to-end trading cycle validation
- **Self-Healing Tests**: 27 tests covering agents, dedup, and anomaly detection
  ```bash
  # Run all self-healing tests
  .venv/bin/python -m pytest tests/integration/test_self_healing_agents.py \
                               tests/integration/test_advanced_self_healing.py -v
  ```

#### Code Quality
- **Type Hints**: Full type annotation using Python typing module
- **Pydantic Models**: Data validation and serialization
- **Logging**: Structured logging with `logging_config.py`

## 📖 Documentation

### Core Documentation
- **Self-Healing Architecture**: [docs/SELF_HEALING_ARCHITECTURE.md](docs/SELF_HEALING_ARCHITECTURE.md) - Complete guide to agent-based architecture
- **Implementation Summary**: [SELF_HEALING_IMPLEMENTATION_SUMMARY.md](SELF_HEALING_IMPLEMENTATION_SUMMARY.md) - What was built and how
- **Bybit Configuration**: [BYBIT_DEMO_TRADING_CONFIGURATION.md](BYBIT_DEMO_TRADING_CONFIGURATION.md) - Bybit demo trading setup guide
- **Migrations**: [migrations/README.md](migrations/README.md)
- **Backups:** `scripts/BACKUP_RESTORE_README.md`
- **Optimization Plan:** `OPTIMIZATION_COMPLETE.md`
- **API Docs:** Available at `/docs` when running FastAPI server

### Archived Documentation
Historical reports and deprecated exchange documentation have been moved to:
- **Deprecated MEXC docs**: `docs_archive/deprecated/` (15 files)
- **Historical reports**: `docs_archive/historical_reports/` (dated status reports)

These documents are preserved for reference but may contain outdated configuration information.

## 🧪 Testing

```bash
python scripts/validate_new_features.py
```

## 📄 License

MIT License

---
**Version:** 2.0.0 (Self-Healing Edition) | **Status:** Production Ready ✅  
**Last Updated:** May 14, 2026 | **Active Exchange:** Bybit (pybit SDK)
