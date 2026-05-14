# =============================================================================
# Auto Trade System - Makefile
# =============================================================================
# Streamlined development, testing, and deployment commands
# =============================================================================

.PHONY: help dev setup test lint deploy logs clean db-migrate db-reset \
        docker-up docker-down docker-build docker-logs docker-clean \
        format check-types coverage pre-commit-install

# =============================================================================
# VARIABLES
# =============================================================================

PYTHON := python3.11
VENV := .venv
VENV_PYTHON := $(VENV)/bin/python
VENV_PIP := $(VENV)/bin/pip
VENV_PYTEST := $(VENV)/bin/pytest
VENV_MYPY := $(VENV)/bin/mypy
VENV_BLACK := $(VENV)/bin/black
VENV_FLAKE8 := $(VENV)/bin/flake8

DOCKER_COMPOSE := docker-compose
APP_NAME := auto-trade-system

# Colors for output
GREEN := \033[0;32m
YELLOW := \033[1;33m
RED := \033[0;31m
BLUE := \033[0;34m
NC := \033[0m # No Color

# =============================================================================
# DEFAULT TARGET
# =============================================================================

help: ## Show this help message
	@echo ""
	@echo "$(BLUE)========================================$(NC)"
	@echo "$(BLUE)Auto Trade System - Makefile Help$(NC)"
	@echo "$(BLUE)========================================$(NC)"
	@echo ""
	@echo "$(GREEN)Development:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""

# =============================================================================
# DEVELOPMENT TARGETS
# =============================================================================

setup: ## Setup development environment (Python venv + dependencies)
	@echo "$(GREEN)🔧 Setting up development environment...$(NC)"
	@echo ""
	
	# Check Python version
	@if ! command -v $(PYTHON) &> /dev/null; then \
		echo "$(RED)❌ Python 3.11 required but not found$(NC)"; \
		exit 1; \
	fi
	@echo "$(GREEN)✅ Python 3.11 detected$(NC)"
	
	# Create virtual environment
	@if [ ! -d "$(VENV)" ]; then \
		echo "$(YELLOW)Creating virtual environment...$(NC)"; \
		$(PYTHON) -m venv $(VENV); \
	else \
		echo "$(GREEN)✅ Virtual environment already exists$(NC)"; \
	fi
	
	# Install dependencies
	@echo "$(YELLOW)Installing dependencies...$(NC)"
	$(VENV_PIP) install --upgrade pip
	$(VENV_PIP) install -r requirements.txt
	@echo "$(GREEN)✅ Dependencies installed$(NC)"
	
	# Setup environment file
	@if [ ! -f .env ]; then \
		echo "$(YELLOW)Creating .env from .env.example...$(NC)"; \
		cp .env.example .env; \
		echo "$(RED)⚠️  Please edit .env with your API keys before running$(NC)"; \
	else \
		echo "$(GREEN)✅ .env file already exists$(NC)"; \
	fi
	
	@echo ""
	@echo "$(GREEN)========================================$(NC)"
	@echo "$(GREEN)✅ Setup complete!$(NC)"
	@echo "$(GREEN)========================================$(NC)"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Edit .env with your API keys"
	@echo "  2. Run: make dev"
	@echo ""

dev: setup ## Start development environment (infrastructure + app)
	@echo "$(GREEN)🚀 Starting development environment...$(NC)"
	@echo ""
	
	# Validate environment
	@echo "$(YELLOW)Validating environment...$(NC)"
	@if ! bash scripts/validate_env.sh; then \
		echo "$(RED)❌ Environment validation failed$(NC)"; \
		exit 1; \
	fi
	@echo ""
	
	# Start infrastructure services
	@echo "$(YELLOW)Starting PostgreSQL and Redis...$(NC)"
	$(DOCKER_COMPOSE) up -d postgres redis
	@echo "$(GREEN)✅ Infrastructure started$(NC)"
	
	# Wait for databases to be ready
	@echo "$(YELLOW)Waiting for databases to be ready...$(NC)"
	@until docker exec trading-postgres pg_isready -U $${DB_USER:-trading} > /dev/null 2>&1; do \
		sleep 2; \
	done
	@echo "$(GREEN)✅ PostgreSQL ready$(NC)"
	
	@until docker exec trading-redis redis-cli ping | grep -q PONG; do \
		sleep 1; \
	done
	@echo "$(GREEN)✅ Redis ready$(NC)"
	@echo ""
	
	# Run database migrations
	@echo "$(YELLOW)Running database migrations...$(NC)"
	$(VENV_PYTHON) -m alembic upgrade head
	@echo "$(GREEN)✅ Migrations complete$(NC)"
	@echo ""
	
	# Start application
	@echo "$(GREEN)🎯 Starting FastAPI application...$(NC)"
	@echo "$(BLUE)   Dashboard: http://localhost:8000/docs$(NC)"
	@echo "$(BLUE)   Metrics:   http://localhost:8000/metrics$(NC)"
	@echo ""
	$(VENV_PYTHON) -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# =============================================================================
# TESTING TARGETS
# =============================================================================

test: ## Run all tests
	@echo "$(GREEN)🧪 Running test suite...$(NC)"
	@echo ""
	$(VENV_PYTEST) tests/ -v --tb=short

test-unit: ## Run unit tests only
	@echo "$(GREEN)🧪 Running unit tests...$(NC)"
	@echo ""
	$(VENV_PYTEST) tests/unit/ -v --tb=short

test-integration: ## Run integration tests only
	@echo "$(GREEN)🧪 Running integration tests...$(NC)"
	@echo ""
	$(VENV_PYTEST) tests/integration/ -v --tb=short

test-chaos: ## Run chaos/resilience tests
	@echo "$(GREEN)🧪 Running chaos tests...$(NC)"
	@echo ""
	$(VENV_PYTEST) tests/integration/test_chaos_network_failures.py -v --tb=short

coverage: ## Run tests with coverage report
	@echo "$(GREEN)📊 Generating coverage report...$(NC)"
	@echo ""
	$(VENV_PYTEST) tests/ --cov=app --cov-report=term-missing --cov-report=html
	@echo ""
	@echo "$(GREEN)HTML report generated in htmlcov/index.html$(NC)"

# =============================================================================
# CODE QUALITY TARGETS
# =============================================================================

lint: ## Run linters (flake8, black check)
	@echo "$(GREEN)🔍 Running linters...$(NC)"
	@echo ""
	@echo "$(YELLOW)Checking code style with flake8...$(NC)"
	$(VENV_FLAKE8) app/ --max-line-length=100 --ignore=E501,W503 || true
	@echo ""
	@echo "$(YELLOW)Checking code formatting with black...$(NC)"
	$(VENV_BLACK) app/ --check || true
	@echo ""
	@echo "$(GREEN)✅ Linting complete$(NC)"

format: ## Auto-format code with black
	@echo "$(GREEN)🎨 Formatting code...$(NC)"
	@echo ""
	$(VENV_BLACK) app/
	@echo "$(GREEN)✅ Code formatted$(NC)"

check-types: ## Run type checker (mypy)
	@echo "$(GREEN)🔍 Running type checker...$(NC)"
	@echo ""
	$(VENV_MYPY) app/ --ignore-missing-imports || true
	@echo ""
	@echo "$(GREEN)✅ Type checking complete$(NC)"

pre-commit-install: ## Install pre-commit hooks
	@echo "$(GREEN)🔧 Installing pre-commit hooks...$(NC)"
	pip install pre-commit
	pre-commit install
	@echo "$(GREEN)✅ Pre-commit hooks installed$(NC)"

# =============================================================================
# DEPLOYMENT TARGETS
# =============================================================================

deploy: ## Deploy to production (systemd services)
	@echo "$(GREEN)🚀 Deploying to production...$(NC)"
	@echo ""
	bash deploy.sh --install

deploy-start: ## Start production services
	@echo "$(GREEN)🚀 Starting production services...$(NC)"
	@echo ""
	bash deploy.sh --start

deploy-stop: ## Stop production services
	@echo "$(YELLOW)⏹️  Stopping production services...$(NC)"
	@echo ""
	bash deploy.sh --stop

deploy-restart: ## Restart production services
	@echo "$(YELLOW)🔄 Restarting production services...$(NC)"
	@echo ""
	bash deploy.sh --restart

deploy-status: ## Check production service status
	@echo "$(BLUE)📊 Production service status:$(NC)"
	@echo ""
	bash deploy.sh --status

# =============================================================================
# DOCKER TARGETS
# =============================================================================

docker-up: ## Start all Docker services (infrastructure + app)
	@echo "$(GREEN)🐳 Starting Docker services...$(NC)"
	@echo ""
	$(DOCKER_COMPOSE) up -d
	@echo "$(GREEN)✅ All services started$(NC)"
	@echo ""
	@echo "Services:"
	@echo "  - PostgreSQL:  localhost:5432"
	@echo "  - Redis:       localhost:6379"
	@echo "  - Prometheus:  localhost:9090"
	@echo "  - Grafana:     localhost:3000"
	@echo "  - Loki:        localhost:3100"
	@echo "  - Trading Bot: localhost:8000"
	@echo ""

docker-down: ## Stop all Docker services
	@echo "$(YELLOW)⏹️  Stopping Docker services...$(NC)"
	@echo ""
	$(DOCKER_COMPOSE) down
	@echo "$(GREEN)✅ All services stopped$(NC)"

docker-build: ## Build Docker images
	@echo "$(GREEN)🔨 Building Docker images...$(NC)"
	@echo ""
	$(DOCKER_COMPOSE) build
	@echo "$(GREEN)✅ Build complete$(NC)"

docker-logs: ## View Docker service logs
	@echo "$(BLUE)📋 Viewing Docker logs...$(NC)"
	@echo ""
	$(DOCKER_COMPOSE) logs -f

docker-logs-api: ## View trading bot API logs
	@echo "$(BLUE)📋 Viewing trading bot API logs...$(NC)"
	@echo ""
	$(DOCKER_COMPOSE) logs -f trading-bot

docker-logs-worker: ## View trading worker logs
	@echo "$(BLUE)📋 Viewing trading worker logs...$(NC)"
	@echo ""
	$(DOCKER_COMPOSE) logs -f trading-worker

docker-clean: ## Remove all Docker containers and volumes
	@echo "$(RED)⚠️  WARNING: This will remove ALL containers and volumes!$(NC)"
	@echo "$(RED)This action cannot be undone.$(NC)"
	@read -p "Are you sure? (y/N): " confirm && [ "$$confirm" = "y" ] || exit 1
	@echo ""
	$(DOCKER_COMPOSE) down -v
	@echo "$(GREEN)✅ Cleanup complete$(NC)"

# =============================================================================
# LOGGING TARGETS
# =============================================================================

logs: ## View application logs (tail -f)
	@echo "$(BLUE)📋 Tailing application logs...$(NC)"
	@echo ""
	tail -f logs/app_*.log 2>/dev/null || echo "$(RED)No log files found$(NC)"

logs-error: ## View error logs only
	@echo "$(BLUE)📋 Tailing error logs...$(NC)"
	@echo ""
	tail -f logs/error_*.log 2>/dev/null || echo "$(RED)No error log files found$(NC)"

logs-json: ## View structured JSON logs
	@echo "$(BLUE)📋 Tailing JSON logs...$(NC)"
	@echo ""
	tail -f logs/json_*.log 2>/dev/null || echo "$(RED)No JSON log files found$(NC)"

logs-clear: ## Clear all log files
	@echo "$(YELLOW)🗑️  Clearing log files...$(NC)"
	find logs/ -name "*.log" -delete
	find logs/ -name "*.log.zip" -delete
	@echo "$(GREEN)✅ Logs cleared$(NC)"

# =============================================================================
# DATABASE TARGETS
# =============================================================================

db-migrate: ## Run database migrations
	@echo "$(GREEN)🗄️  Running database migrations...$(NC)"
	@echo ""
	$(VENV_PYTHON) -m alembic upgrade head
	@echo "$(GREEN)✅ Migrations complete$(NC)"

db-reset: ## Reset database (WARNING: Deletes all data!)
	@echo "$(RED)⚠️  WARNING: This will DELETE ALL DATA!$(NC)"
	@echo "$(RED)This action cannot be undone.$(NC)"
	@read -p "Are you sure? (y/N): " confirm && [ "$$confirm" = "y" ] || exit 1
	@echo ""
	@echo "$(YELLOW)Dropping all tables...$(NC)"
	$(VENV_PYTHON) -m alembic downgrade base
	@echo "$(YELLOW)Re-running migrations...$(NC)"
	$(VENV_PYTHON) -m alembic upgrade head
	@echo "$(GREEN)✅ Database reset complete$(NC)"

db-backup: ## Backup database
	@echo "$(GREEN)💾 Backing up database...$(NC)"
	@mkdir -p backups
	@BACKUP_FILE="backups/vmassit_$$(date +%Y%m%d_%H%M%S).sql.gz"; \
	docker exec trading-postgres pg_dump -U $${DB_USER:-trading} $${DB_NAME:-vmassit} | gzip > $$BACKUP_FILE; \
	echo "$(GREEN)✅ Backup saved to $$BACKUP_FILE$(NC)"

# =============================================================================
# CLEANUP TARGETS
# =============================================================================

clean: ## Clean up temporary files
	@echo "$(YELLOW)🗑️  Cleaning up...$(NC)"
	@echo ""
	
	# Remove Python cache
	@echo "$(YELLOW)Removing Python cache...$(NC)"
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	
	# Remove pytest cache
	@echo "$(YELLOW)Removing pytest cache...$(NC)"
	rm -rf .pytest_cache 2>/dev/null || true
	rm -rf htmlcov 2>/dev/null || true
	rm -f .coverage 2>/dev/null || true
	
	# Remove mypy cache
	@echo "$(YELLOW)Removing mypy cache...$(NC)"
	rm -rf .mypy_cache 2>/dev/null || true
	
	# Remove build artifacts
	@echo "$(YELLOW)Removing build artifacts...$(NC)"
	rm -rf build/ 2>/dev/null || true
	rm -rf dist/ 2>/dev/null || true
	rm -rf *.egg-info 2>/dev/null || true
	
	@echo "$(GREEN)✅ Cleanup complete$(NC)"

clean-all: clean ## Clean everything including venv
	@echo "$(RED)⚠️  Removing virtual environment...$(NC)"
	rm -rf $(VENV)
	@echo "$(GREEN)✅ Full cleanup complete$(NC)"

# =============================================================================
# UTILITY TARGETS
# =============================================================================

health: ## Check health of all services
	@echo "$(BLUE)🏥 Checking service health...$(NC)"
	@echo ""
	@echo "$(YELLOW)PostgreSQL:$(NC)"
	@docker exec trading-postgres pg_isready -U $${DB_USER:-trading} 2>/dev/null && echo "$(GREEN)✅ Healthy$(NC)" || echo "$(RED)❌ Unhealthy$(NC)"
	@echo ""
	@echo "$(YELLOW)Redis:$(NC)"
	@docker exec trading-redis redis-cli ping 2>/dev/null | grep -q PONG && echo "$(GREEN)✅ Healthy$(NC)" || echo "$(RED)❌ Unhealthy$(NC)"
	@echo ""
	@echo "$(YELLOW)Trading Bot API:$(NC)"
	@curl -f http://localhost:8000/api/v1/health > /dev/null 2>&1 && echo "$(GREEN)✅ Healthy$(NC)" || echo "$(RED)❌ Unhealthy$(NC)"
	@echo ""
	@echo "$(YELLOW)Prometheus:$(NC)"
	@curl -f http://localhost:9090/-/healthy > /dev/null 2>&1 && echo "$(GREEN)✅ Healthy$(NC)" || echo "$(RED)❌ Unhealthy$(NC)"
	@echo ""
	@echo "$(YELLOW)Grafana:$(NC)"
	@curl -f http://localhost:3000/api/health > /dev/null 2>&1 && echo "$(GREEN)✅ Healthy$(NC)" || echo "$(RED)❌ Unhealthy$(NC)"
	@echo ""

stats: ## Show project statistics
	@echo "$(BLUE)📊 Project Statistics$(NC)"
	@echo ""
	@echo "$(YELLOW)Python Files:$(NC)"
	@find app/ -name "*.py" | wc -l
	@echo ""
	@echo "$(YELLOW)Test Files:$(NC)"
	@find tests/ -name "*.py" | wc -l
	@echo ""
	@echo "$(YELLOW)Total Lines of Code:$(NC)"
	@find app/ -name "*.py" -exec cat {} + | wc -l
	@echo ""
	@echo "$(YELLOW)Total Test Lines:$(NC)"
	@find tests/ -name "*.py" -exec cat {} + | wc -l
	@echo ""

# =============================================================================
# END OF MAKEFILE
# =============================================================================
