# VMassit Database Backup & Restore System

Automated backup and restore system for the VMassit SQLite database with compression, verification, and rotation.

## Quick Start

### Manual Backup
```bash
cd /home/admin/.openclaw/workspace/VMassit/VMassit/VMassit
./scripts/backup_database.sh
```

### List Available Backups
```bash
./scripts/restore_database.sh --list
```

### Restore Latest Backup
```bash
./scripts/restore_database.sh --latest
```

### Restore Specific Backup
```bash
./scripts/restore_database.sh data/backups/vmassit_db_20260510_120000.db.gz
```

## Features

✅ **Automated Daily Backups** - Via systemd timer  
✅ **Compression** - Gzip compression saves ~90% space  
✅ **Integrity Verification** - Validates backups after creation  
✅ **Automatic Rotation** - Configurable retention period (default: 30 days)  
✅ **Pre-Restore Safety** - Creates backup before restoring  
✅ **Service Management** - Automatically stops/starts API during restore  

## Backup Script Options

```bash
./scripts/backup_database.sh [options]

Options:
  --retention DAYS    Number of days to keep backups (default: 30)
  --backup-dir DIR    Backup directory (default: data/backups)
  --help              Show help message
```

### Examples

Backup with 7-day retention:
```bash
./scripts/backup_database.sh --retention 7
```

Backup to custom directory:
```bash
./scripts/backup_database.sh --backup-dir /mnt/external-backups
```

## Restore Script Options

```bash
./scripts/restore_database.sh [backup_file] [options]

Options:
  --list              List available backups
  --latest            Use the most recent backup
  --backup-dir DIR    Backup directory (default: data/backups)
  --force             Skip confirmation prompt
  --help              Show help message
```

### Examples

List all backups:
```bash
./scripts/restore_database.sh --list
```

Restore latest backup (with confirmation):
```bash
./scripts/restore_database.sh --latest
```

Force restore without confirmation:
```bash
./scripts/restore_database.sh --latest --force
```

## Automated Backups (Systemd Timer)

The system includes a systemd timer that runs daily backups automatically.

### Enable Automated Backups

```bash
# Copy service files to systemd directory
sudo cp systemd/vmassit-backup.service /etc/systemd/system/
sudo cp systemd/vmassit-backup.timer /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable and start the timer
sudo systemctl enable vmassit-backup.timer
sudo systemctl start vmassit-backup.timer

# Check timer status
systemctl list-timers vmassit-backup.timer
```

### Check Backup Status

```bash
# View timer status
systemctl status vmassit-backup.timer

# View last backup logs
journalctl -u vmassit-backup.service -n 50

# List all timers
systemctl list-timers --all
```

### Disable Automated Backups

```bash
sudo systemctl stop vmassit-backup.timer
sudo systemctl disable vmassit-backup.timer
```

## Backup File Format

Backups are stored as compressed gzip files:
```
data/backups/vmassit_db_YYYYMMDD_HHMMSS.db.gz
```

Example:
```
vmassit_db_20260510_143022.db.gz
```

## Backup Storage

### Default Location
```
/home/admin/.openclaw/workspace/VMassit/VMassit/VMassit/data/backups/
```

### Disk Usage
Check current backup storage usage:
```bash
du -sh data/backups/
```

List backups by size:
```bash
ls -lhS data/backups/vmassit_db_*.db.gz
```

## Best Practices

### Before Major Updates
Always create a manual backup before applying migrations or updates:
```bash
./scripts/backup_database.sh
.venv/bin/python migrate.py upgrade
```

### Regular Testing
Periodically test your backups by restoring to a temporary location:
```bash
# Create temp directory
mkdir -p /tmp/test-restore

# Restore backup to temp location
gunzip -c data/backups/vmassit_db_LATEST.db.gz > /tmp/test-restore/test.db

# Verify
sqlite3 /tmp/test-restore/test.db "SELECT count(*) FROM sqlite_master;"

# Cleanup
rm -rf /tmp/test-restore
```

### Off-Site Backups
For production deployments, copy backups to off-site storage:
```bash
# Example: Copy to remote server
scp data/backups/vmassit_db_*.db.gz user@backup-server:/backups/vmassit/

# Example: Upload to S3 (requires AWS CLI)
aws s3 sync data/backups/ s3://my-backup-bucket/vmassit/
```

### Monitoring
Set up monitoring for backup failures:
```bash
# Check if backup ran today
if ! ls data/backups/vmassit_db_$(date +%Y%m%d)*.db.gz >/dev/null 2>&1; then
    echo "WARNING: No backup found for today!" | mail -s "Backup Alert" admin@example.com
fi
```

## Troubleshooting

### Backup Fails with "Database Locked"
Stop the API service before backing up:
```bash
sudo systemctl stop vmassit-api
./scripts/backup_database.sh
sudo systemctl start vmassit-api
```

### Restore Fails
1. Check backup integrity:
   ```bash
   gzip -t data/backups/YOUR_BACKUP.db.gz
   ```

2. Check disk space:
   ```bash
   df -h data/
   ```

3. Check file permissions:
   ```bash
   ls -la data/vmassit.db
   chmod 644 data/vmassit.db
   ```

### Automatic Backups Not Running
Check timer status:
```bash
systemctl status vmassit-backup.timer
journalctl -u vmassit-backup.timer -n 50
```

Enable timer if disabled:
```bash
sudo systemctl enable vmassit-backup.timer
sudo systemctl start vmassit-backup.timer
```

### Recovering from Corruption
If database is corrupted and no backup exists:
```bash
# Try SQLite recovery
sqlite3 data/vmassit.db ".recover" > recovered.sql

# Create new database
rm data/vmassit.db
sqlite3 data/vmassit.db < recovered.sql

# Apply migrations
.venv/bin/python migrate.py upgrade
```

## Backup Retention Policy

Default retention: **30 days**

Adjust based on your needs:
- **Development**: 7 days (save space)
- **Staging**: 14 days
- **Production**: 30-90 days (compliance)

Change retention in systemd service:
```bash
# Edit service file
sudo nano /etc/systemd/system/vmassit-backup.service

# Change this line:
ExecStart=.../backup_database.sh --retention 90

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl restart vmassit-backup.timer
```

## Security Considerations

✅ Backups are stored locally with same permissions as database  
✅ No sensitive data is transmitted (local only)  
⚠️ For production: Encrypt backups containing sensitive data  
⚠️ For production: Use secure off-site storage  

To encrypt backups (optional):
```bash
# Encrypt backup with GPG
gpg --symmetric --cipher-algo AES256 data/backups/vmassit_db_*.db.gz

# Decrypt when needed
gpg --decrypt data/backups/vmassit_db_*.db.gz.gpg | gunzip > data/vmassit.db
```

## Integration with Migration System

The backup system works seamlessly with the Alembic migration system:

```bash
# Safe update workflow:
./scripts/backup_database.sh          # Backup first
.venv/bin/python migrate.py upgrade   # Apply migrations
./scripts/backup_database.sh          # Backup after
```

If migration fails:
```bash
./scripts/restore_database.sh --latest  # Restore pre-migration state
```

## Monitoring & Alerts

### Check Backup Health
```bash
#!/bin/bash
# backup_health_check.sh

BACKUP_DIR="data/backups"
TODAY=$(date +%Y%m%d)

if ls "${BACKUP_DIR}"/vmassit_db_${TODAY}*.db.gz >/dev/null 2>&1; then
    echo "✓ Today's backup exists"
else
    echo "✗ No backup found for today"
    exit 1
fi

# Check backup age
LATEST=$(ls -t "${BACKUP_DIR}"/vmassit_db_*.db.gz | head -1)
AGE=$(( ($(date +%s) - $(stat -c %Y "$LATEST")) / 3600 ))

if [ $AGE -lt 24 ]; then
    echo "✓ Latest backup is ${AGE} hours old"
else
    echo "✗ Latest backup is ${AGE} hours old (>24h)"
    exit 1
fi
```

## Summary

The VMassit backup system provides:
- ✅ Automated daily backups via systemd timer
- ✅ Manual backup/restore commands
- ✅ Compression and integrity verification
- ✅ Automatic rotation (configurable retention)
- ✅ Safe restore with pre-restore backup
- ✅ Service management integration

For questions or issues, check:
- Logs: `journalctl -u vmassit-backup.service`
- Timer: `systemctl status vmassit-backup.timer`
- Backups: `ls -lh data/backups/`
