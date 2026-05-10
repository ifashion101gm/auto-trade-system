#!/bin/bash
# VMassit Database Backup Script
# 
# Creates timestamped backups of the VMassit SQLite database
# with compression and rotation.
#
# Usage:
#   ./backup_database.sh [options]
#
# Options:
#   --retention DAYS    Number of days to keep backups (default: 30)
#   --backup-dir DIR    Backup directory (default: data/backups)
#   --help              Show this help message

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DB_PATH="${PROJECT_ROOT}/data/vmassit.db"
BACKUP_DIR="${PROJECT_ROOT}/data/backups"
RETENTION_DAYS=30
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="vmassit_db_${TIMESTAMP}.db.gz"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --retention)
            RETENTION_DAYS="$2"
            shift 2
            ;;
        --backup-dir)
            BACKUP_DIR="$2"
            shift 2
            ;;
        --help)
            head -20 "$0" | grep '^#' | sed 's/^# //'
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
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

# Check if database exists
if [ ! -f "$DB_PATH" ]; then
    log_error "Database not found at: $DB_PATH"
    exit 1
fi

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

log_info "Starting database backup..."
log_info "Database: $DB_PATH"
log_info "Backup: $BACKUP_DIR/$BACKUP_FILE"
log_info "Retention: $RETENTION_DAYS days"

# Create compressed backup
log_info "Compressing and copying database..."
if gzip -c "$DB_PATH" > "${BACKUP_DIR}/${BACKUP_FILE}"; then
    BACKUP_SIZE=$(du -h "${BACKUP_DIR}/${BACKUP_FILE}" | cut -f1)
    log_info "Backup created successfully (${BACKUP_SIZE})"
else
    log_error "Backup failed!"
    exit 1
fi

# Verify backup integrity
log_info "Verifying backup integrity..."
if gzip -t "${BACKUP_DIR}/${BACKUP_FILE}" 2>/dev/null; then
    log_info "Backup integrity verified ✓"
else
    log_error "Backup verification failed! File may be corrupted."
    rm -f "${BACKUP_DIR}/${BACKUP_FILE}"
    exit 1
fi

# Clean up old backups
log_info "Cleaning up backups older than $RETENTION_DAYS days..."
OLD_BACKUPS=$(find "$BACKUP_DIR" -name "vmassit_db_*.db.gz" -type f -mtime +$RETENTION_DAYS 2>/dev/null | wc -l)

if [ "$OLD_BACKUPS" -gt 0 ]; then
    find "$BACKUP_DIR" -name "vmassit_db_*.db.gz" -type f -mtime +$RETENTION_DAYS -delete
    log_info "Removed $OLD_BACKUPS old backup(s)"
else
    log_info "No old backups to remove"
fi

# List current backups
log_info "Current backups:"
ls -lh "${BACKUP_DIR}"/vmassit_db_*.db.gz 2>/dev/null | tail -5 || echo "  No backups found"

# Show disk usage
TOTAL_BACKUP_SIZE=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1)
log_info "Total backup storage used: $TOTAL_BACKUP_SIZE"

log_info "Backup completed successfully! ✓"
exit 0
