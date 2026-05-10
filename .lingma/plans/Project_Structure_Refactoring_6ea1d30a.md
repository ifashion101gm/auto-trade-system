# Project Structure Refactoring Plan

## 1. Configuration Management
- **Create `app/config.py`**: Implement a centralized configuration class using `pydantic-settings`. This will replace scattered `os.getenv()` calls and provide type-safe access to environment variables like `DATABASE_URL`, `TRADING_API_SECRET`, and Redis URLs.
- **Update `app/main.py`**: Initialize the configuration at startup and pass it to dependent modules.

## 2. Database & ORM Layer
- **Create `app/storage/models.py`**: Define SQLAlchemy ORM models for all tables currently managed by raw SQL in `migrations/versions/001_initial_schema.py`. This includes `ModelUsage`, `AssistantMemory`, `PaperTrades`, etc.
- **Refactor `app/storage/db.py`**: 
  - Import the new `Base` and models.
  - Remove the redundant synchronous engine used for SQLite PRAGMAs; instead, use an event listener on the async engine to ensure WAL mode is enabled consistently.
  - Ensure the `init_db` function uses the ORM `Base.metadata`.

## 3. Package Standardization
- **Add `__init__.py` files**: Create empty `__init__.py` files in all subdirectories of `app/` (`api`, `ai`, `cache`, `infra`, `learning`, `llm`, `storage`) to ensure they are recognized as proper Python packages.
- **Clean up `migrations/`**: Remove the duplicate/empty `migrations/README` file, keeping only `migrations/README.md`.

## 4. Decoupling & Dependency Injection
- **Refactor API Routers**: Update endpoints in `app/api/` to use dependency injection for shared resources (like the `RateLimiter`, `ThreeTierCache`, and `LLMSpendTracker`) instead of relying on global module-level instances. This improves testability and prevents state leakage.
- **Standardize Imports**: Ensure all internal imports use absolute paths (e.g., `from app.storage.models import ...`) to avoid circular dependency issues.

## 5. Documentation Updates
- **Update `README.md`**: Reflect the new project structure, including the addition of the ORM layer and centralized configuration.
- **Align with "Zone" Architecture**: Ensure the documentation in `OPTIMIZATION_COMPLETE.md` is referenced or updated to show how the new structure supports the 5-zone optimization plan.

## Summary of Changes
- **New Files**: `app/config.py`, `app/storage/models.py`, various `__init__.py` files.
- **Modified Files**: `app/storage/db.py`, `app/main.py`, `app/api/*.py`, `migrations/env.py`, `README.md`.
- **Deleted Files**: `migrations/README` (duplicate).