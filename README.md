# Auto Trade System - Infrastructure Components

Production-ready database management, backup systems, and data portability infrastructure for automated trading systems.

## 🎯 Overview

This repository contains enterprise-grade infrastructure components for automated trading systems, providing robust data management, disaster recovery, and monitoring capabilities.

## ✨ Features

### 1. Database Migration System (Alembic)
- Version-controlled schema management
- Safe upgrade/downgrade paths  
- CLI tool for easy operations
- SQLite database support with WAL mode

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

## 🚀 Quick Start

```bash
# Clone and setup
git clone <your-repo-url>
cd auto-trade-system
python -m venv .venv
source .venv/bin/activate
pip install alembic fastapi sqlalchemy

# Run migrations
python migrate.py upgrade

# Create backup
./scripts/backup_database.sh

# Enable automated backups
sudo systemctl enable --now vmassit-backup.timer
```

## 📖 Documentation

- **Migrations:** `migrations/README.md`
- **Backups:** `scripts/BACKUP_RESTORE_README.md`
- **API Docs:** Available at `/docs` when running FastAPI server

## 🧪 Testing

```bash
python scripts/validate_new_features.py
```

## 📄 License

MIT License

---
**Version:** 1.0.0 | **Status:** Production Ready ✅
