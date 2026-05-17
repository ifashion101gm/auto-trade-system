#!/bin/bash
###############################################################################
# Workspace Backup Script for Auto-Trade-System
# Purpose: Automated backup of project files and configurations
# Usage: ./backup_workspace.sh
# Schedule: Recommended daily via cron (0 2 * * *)
###############################################################################

set -e  # Exit on error

# Configuration
WORKSPACE="/home/admin/.openclaw/workspace/auto-trade-system"
BACKUP_DIR="$HOME/backups/auto-trade-system"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=7  # Keep backups for 7 days

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Auto-Trade-System Workspace Backup${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Step 1: Backup project files (excluding large/unnecessary directories)
echo -e "${YELLOW}[1/3] Backing up project files...${NC}"
PROJECT_BACKUP="$BACKUP_DIR/project_$TIMESTAMP.tar.gz"

tar czf "$PROJECT_BACKUP" \
    --exclude='.venv' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='logs/*' \
    --exclude='.pytest_cache' \
    --exclude='.coverage' \
    --exclude='data/*.db' \
    --exclude='data/*.sqlite' \
    --exclude='node_modules' \
    --exclude='.git' \
    -C "$WORKSPACE" .

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Project backup created: $PROJECT_BACKUP${NC}"
    echo "  Size: $(du -h "$PROJECT_BACKUP" | cut -f1)"
else
    echo -e "${RED}✗ Project backup failed${NC}"
    exit 1
fi
echo ""

# Step 2: Backup configuration files
echo -e "${YELLOW}[2/3] Backing up configuration files...${NC}"
CONFIG_BACKUP="$BACKUP_DIR/configs_$TIMESTAMP.tar.gz"

tar czf "$CONFIG_BACKUP" \
    ~/.tmux.conf \
    ~/.bashrc \
    "$WORKSPACE/.env" 2>/dev/null || true

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Configuration backup created: $CONFIG_BACKUP${NC}"
    echo "  Size: $(du -h "$CONFIG_BACKUP" | cut -f1)"
else
    echo -e "${YELLOW}⚠ Some config files may not exist (this is OK)${NC}"
fi
echo ""

# Step 3: Backup database (if exists)
echo -e "${YELLOW}[3/3] Backing up databases...${NC}"
DB_BACKUP="$BACKUP_DIR/databases_$TIMESTAMP.tar.gz"
DB_FOUND=false

# Check for SQLite databases
if ls "$WORKSPACE/data/"*.db 1> /dev/null 2>&1; then
    tar czf "$DB_BACKUP" -C "$WORKSPACE" data/*.db 2>/dev/null || true
    DB_FOUND=true
fi

if ls "$WORKSPACE/data/"*.sqlite 1> /dev/null 2>&1; then
    if [ "$DB_FOUND" = false ]; then
        tar czf "$DB_BACKUP" -C "$WORKSPACE" data/*.sqlite 2>/dev/null || true
    else
        tar rzf "$DB_BACKUP" -C "$WORKSPACE" data/*.sqlite 2>/dev/null || true
    fi
    DB_FOUND=true
fi

if [ "$DB_FOUND" = true ]; then
    echo -e "${GREEN}✓ Database backup created: $DB_BACKUP${NC}"
    echo "  Size: $(du -h "$DB_BACKUP" | cut -f1)"
else
    echo -e "${YELLOW}⚠ No databases found to backup${NC}"
    rm -f "$DB_BACKUP" 2>/dev/null || true
fi
echo ""

# Cleanup old backups
echo -e "${YELLOW}Cleaning up old backups (keeping last $RETENTION_DAYS days)...${NC}"
find "$BACKUP_DIR" -name "*.tar.gz" -type f -mtime +$RETENTION_DAYS -delete 2>/dev/null || true
REMAINING=$(ls -1 "$BACKUP_DIR"/*.tar.gz 2>/dev/null | wc -l)
echo -e "${GREEN}✓ Remaining backups: $REMAINING${NC}"
echo ""

# Summary
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Backup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Backup location: $BACKUP_DIR"
echo "Timestamp: $TIMESTAMP"
echo ""
echo "Backup contents:"
ls -lh "$BACKUP_DIR"/*"$TIMESTAMP".tar.gz 2>/dev/null || echo "No backups found"
echo ""
echo -e "${YELLOW}Tip: To restore a backup:${NC}"
echo "  tar xzf $BACKUP_DIR/project_$TIMESTAMP.tar.gz -C /path/to/restore/"
echo ""
