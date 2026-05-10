# VMassit Database Migration System

This directory contains the Alembic-based database migration system for VMassit.

## Quick Start

### Apply All Pending Migrations
```bash
cd /home/admin/.openclaw/workspace/VMassit/VMassit/VMassit
.venv/bin/python migrate.py upgrade
```

### Check Current Migration Status
```bash
.venv/bin/python migrate.py status
```

### View Migration History
```bash
.venv/bin/python migrate.py history
```

### Rollback Last Migration
```bash
.venv/bin/python migrate.py downgrade
```

### Create New Migration
```bash
.venv/bin/python migrate.py revision "description of changes"
```

## Directory Structure

```
migrations/
├── env.py                    # Alembic environment configuration
├── README                    # This file
├── script.py.mako            # Template for new migrations
└── versions/                 # Migration scripts
    ├── 001_initial_schema.py # Initial database schema
    └── ...                   # Future migrations
```

## How It Works

1. **Migration Scripts**: Each file in `versions/` represents a database change
2. **Version Tracking**: Alembic tracks which migrations have been applied
3. **Upgrade/Downgrade**: Each migration has both upgrade and downgrade functions
4. **Safe Updates**: You can safely update the database schema without data loss

## Best Practices

### Creating New Migrations

1. Make your changes to the database schema in `app/storage/db.py`
2. Generate a new migration:
   ```bash
   .venv/bin/python migrate.py revision "add new table XYZ"
   ```
3. Review the generated migration file in `versions/`
4. Test the migration:
   ```bash
   .venv/bin/python migrate.py upgrade
   .venv/bin/python migrate.py downgrade
   .venv/bin/python migrate.py upgrade
   ```

### Updating Existing Deployments

When deploying updates:
```bash
# Backup database first (see ../scripts/backup_database.sh)
./scripts/backup_database.sh

# Apply migrations
.venv/bin/python migrate.py upgrade

# Verify application works
systemctl restart vmassit-api
systemctl status vmassit-api
```

## Troubleshooting

### Migration Fails with "Database Locked"
- Ensure no other process is using the database
- Stop the API service before migrating:
  ```bash
  sudo systemctl stop vmassit-api
  .venv/bin/python migrate.py upgrade
  sudo systemctl start vmassit-api
  ```

### Need to Reset Migrations
**WARNING: This will delete all data!**
```bash
rm data/vmassit.db
.venv/bin/python migrate.py upgrade
```

### Check Migration Version
```bash
.venv/bin/python migrate.py current
```

## Migration Commands Reference

| Command | Description |
|---------|-------------|
| `migrate.py upgrade` | Apply all pending migrations |
| `migrate.py downgrade` | Rollback last migration |
| `migrate.py status` | Show current migration status |
| `migrate.py history` | Show migration history |
| `migrate.py current` | Show current version |
| `migrate.py revision "desc"` | Create new migration |

## For Developers

### Autogenerate Migrations
Alembic can automatically detect schema changes:
```bash
.venv/bin/python migrate.py revision "auto" --autogenerate
```

Note: Autogenerate works best with SQLAlchemy ORM models. Since VMassit uses raw SQL, you may need to manually edit generated migrations.

### Testing Migrations
Always test both upgrade and downgrade:
```bash
# Test upgrade
.venv/bin/python migrate.py upgrade

# Test downgrade
.venv/bin/python migrate.py downgrade

# Re-apply
.venv/bin/python migrate.py upgrade
```

## Schema Documentation

Current tables (as of migration 001):
- `model_usage` - LLM API call tracking
- `assistant_memory` - Conversation history
- `decision_journal` - AI decision logging
- `strategy_registry` - Strategy metadata
- `strategy_evaluations` - Strategy performance scores
- `paper_trades` - Paper trading records
- `trail_events` - Trailing stop adjustments
- `trade_proposals` - Trade signal proposals
- `strategy_parameters` - Parameter version control
- `backtest_runs` - Backtest results
- `optimization_runs` - Optimization run tracking
- `performance_periods` - Aggregated performance metrics
- `optimization_results` - Optimization result rankings
- `schema_migrations` - Migration version tracking

See `versions/001_initial_schema.py` for complete schema details.
