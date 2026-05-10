#!/bin/bash
# VMassit Database Restore Script
#
# Restores a VMassit database from a backup file.
#
# Usage:
#   ./restore_database.sh [backup_file] [options]
#
# Options:
#   --list              List available backups
#   --latest            Use the most recent backup
#   --backup-dir DIR    Backup directory (default: data/backups)
#   --force             Skip confirmation prompt
#   --help              Show this help message

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DB_PATH="${PROJECT_ROOT}/data/vmassit.db"
BACKUP_DIR="${PROJECT_ROOT}/data/backups"
USE_LATEST=false
FORCE=false
BACKUP_FILE=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --list)
            echo "Available backups:"
            if ls "${BACKUP_DIR}"/vmassit_db_*.db.gz 1>/dev/null 2>&1; then
                ls -lht "${BACKUP_DIR}"/vmassit_db_*.db.gz | head -20
            else
                echo "  No backups found in $BACKUP_DIR"
            fi
            exit 0
            ;;
        --latest)
            USE_LATEST=true
            shift
            ;;
        --backup-dir)
            BACKUP_DIR="$2"
            shift 2
            ;;
        --force)
            FORCE=true
            shift
            ;;
        --help)
            head -20 "$0" | grep '^#' | sed 's/^# //'
            exit 0
            ;;
        -*)
            echo "Unknown option: $1"
            exit 1
            ;;
        *)
            BACKUP_FILE="$1"
            shift
            ;;
    esac
done

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# If no backup file specified and not using latest, show error
if [ -z "$BACKUP_FILE" ] && [ "$USE_LATEST" = false ]; then
    log_error "No backup file specified!"
    echo ""
    echo "Usage:"
    echo "  ./restore_database.sh --latest          # Restore most recent backup"
    echo "  ./restore_database.sh <backup_file>     # Restore specific backup"
    echo "  ./restore_database.sh --list            # List available backups"
    echo ""
    exit 1
fi

# Find latest backup if requested
if [ "$USE_LATEST" = true ]; then
    BACKUP_FILE=$(ls -t "${BACKUP_DIR}"/vmassit_db_*.db.gz 2>/dev/null | head -1)
    if [ -z "$BACKUP_FILE" ]; then
        log_error "No backups found in $BACKUP_DIR"
        exit 1
    fi
    log_info "Using latest backup: $(basename "$BACKUP_FILE")"
fi

# Check if backup file exists
if [ ! -f "$BACKUP_FILE" ]; then
    log_error "Backup file not found: $BACKUP_FILE"
    exit 1
fi

# Verify backup integrity
log_info "Verifying backup integrity..."
if ! gzip -t "$BACKUP_FILE" 2>/dev/null; then
    log_error "Backup file is corrupted!"
    exit 1
fi
log_info "Backup integrity verified ✓"

# Warn about data loss
if [ "$FORCE" = false ]; then
    log_warn "WARNING: This will OVERWRITE the current database!"
    echo ""
    echo "Current database: $DB_PATH"
    if [ -f "$DB_PATH" ]; then
        CURRENT_SIZE=$(du -h "$DB_PATH" | cut -f1)
        echo "Current size: $CURRENT_SIZE"
    else
        echo "Current database does not exist"
    fi
    echo ""
    echo "Backup file: $BACKUP_FILE"
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "Backup size: $BACKUP_SIZE"
    echo ""
    read -p "Are you sure you want to continue? (yes/no): " CONFIRM
    if [ "$CONFIRM" != "yes" ]; then
        log_info "Restore cancelled"
        exit 0
    fi
fi

# Stop API service if running
log_info "Checking if VMassit API is running..."
if systemctl is-active --quiet vmassit-api 2>/dev/null; then
    log_warn "VMassit API is running. Stopping service..."
    sudo systemctl stop vmassit-api
    STOPPED_SERVICE=true
else
    STOPPED_SERVICE=false
fi

# Create backup of current database before restoring
if [ -f "$DB_PATH" ]; then
    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    PRE_RESTORE_BACKUP="${DB_PATH}.pre_restore_${TIMESTAMP}.bak"
    log_info "Creating pre-restore backup: $PRE_RESTORE_BACKUP"
    cp "$DB_PATH" "$PRE_RESTORE_BACKUP"
fi

# Restore database
log_info "Restoring database from backup..."
if gunzip -c "$BACKUP_FILE" > "$DB_PATH"; then
    log_info "Database restored successfully ✓"
else
    log_error "Restore failed!"
    # Try to restore pre-restore backup if it exists
    if [ -n "${PRE_RESTORE_BACKUP:-}" ] && [ -f "$PRE_RESTORE_BACKUP" ]; then
        log_warn "Attempting to restore previous state..."
        cp "$PRE_RESTORE_BACKUP" "$DB_PATH"
    fi
    exit 1
fi

# Verify restored database
log_info "Verifying restored database..."
if sqlite3 "$DB_PATH" "SELECT count(*) FROM sqlite_master;" >/dev/null 2>&1; then
    TABLE_COUNT=$(sqlite3 "$DB_PATH" "SELECT count(*) FROM sqlite_master WHERE type='table';")
    log_info "Database verification passed ($TABLE_COUNT tables found) ✓"
else
    log_error "Restored database appears to be corrupted!"
    exit 1
fi

# Restart API service if we stopped it
if [ "$STOPPED_SERVICE" = true ]; then
    log_info "Restarting VMassit API service..."
    sudo systemctl start vmassit-api
    sleep 2
    if systemctl is-active --quiet vmassit-api 2>/dev/null; then
        log_info "VMassit API service started successfully ✓"
    else
        log_warn "VMassit API service failed to start. Check logs with: journalctl -u vmassit-api -n 50"
    fi
fi

# Show database info
log_info "Restored database information:"
echo "  Location: $DB_PATH"
echo "  Size: $(du -h "$DB_PATH" | cut -f1)"
echo "  Tables: $TABLE_COUNT"
echo ""
log_info "Restore completed successfully! ✓"

exit 0
