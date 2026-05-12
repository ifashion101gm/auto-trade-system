# Auto Trade System - Infrastructure Components

Production-ready database management, backup systems, and data portability infrastructure for automated trading systems.

## 🎯 Overview

This repository contains enterprise-grade infrastructure components for automated trading systems, providing robust data management, disaster recovery, and monitoring capabilities. The system is built using a "Zone" architecture to ensure scalability, security, and cost-efficiency.

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
- MEXC Futures (Primary) with testnet and live modes
- Binance Testnet for paper trading validation
- Bybit integration support
- CCXT-based exchange abstraction layer

### 7. Real-Time Monitoring Stack
- Prometheus metrics collection
- Grafana dashboards for visualization
- WebSocket-based real-time position updates
- Telegram notifications for trade events

## 🚀 Quick Start

```bash
# Clone and setup
git clone <your-repo-url>
cd auto-trade-system
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run migrations
python migrate.py upgrade

# Create backup
./scripts/backup_database.sh

# Enable automated backups
sudo systemctl enable --now vmassit-backup.timer
```

## 📚 Installation & Technology References

This section provides direct links to official documentation for all core technologies used in the Auto Trade System.

### Core Technologies

#### 1. Python Async Programming
The system leverages Python's `asyncio` library for high-performance, non-blocking I/O operations essential for real-time trading.

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
- **CCXT Library**: [CCXT Documentation](https://docs.ccxt.com/) (version 4.5.18)
  - Unified crypto exchange API abstraction
  - Supports MEXC, Binance, Bybit, and 100+ exchanges
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

#### Code Quality
- **Type Hints**: Full type annotation using Python typing module
- **Pydantic Models**: Data validation and serialization
- **Logging**: Structured logging with `logging_config.py`

## 📖 Documentation

- **Migrations:** `migrations/README.md`
- **Backups:** `scripts/BACKUP_RESTORE_README.md`
- **Optimization Plan:** `OPTIMIZATION_COMPLETE.md`
- **API Docs:** Available at `/docs` when running FastAPI server

## 🧪 Testing

```bash
python scripts/validate_new_features.py
```

## 📄 License

MIT License

---
**Version:** 1.0.0 | **Status:** Production Ready ✅
