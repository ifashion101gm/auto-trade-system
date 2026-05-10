#!/bin/bash
# VPS Storage Cleanup Script
# This script cleans up unnecessary files to free disk space
# Run with: bash cleanup_vps_storage.sh

echo "=========================================="
echo "VPS Storage Cleanup Script"
echo "=========================================="
echo ""

# Function to show disk usage before and after
show_disk_usage() {
    echo "Current disk usage:"
    df -h / | tail -1
    echo ""
}

echo "📊 Disk usage before cleanup:"
show_disk_usage

# Priority 1: High Impact Items
echo "🔧 Priority 1: High Impact Cleanup"
echo "-----------------------------------"

# 1. Remove Python 3.11 source code (448 MB)
echo "1. Removing Python 3.11 source code..."
if [ -d "/usr/src/Python-3.11.0" ]; then
    sudo rm -rf /usr/src/Python-3.11.0
    echo "   ✅ Removed /usr/src/Python-3.11.0"
fi
if [ -f "/usr/src/Python-3.11.0.tgz" ]; then
    sudo rm -f /usr/src/Python-3.11.0.tgz
    echo "   ✅ Removed /usr/src/Python-3.11.0.tgz"
fi

# 2. Clean DNF cache (201 MB)
echo "2. Cleaning DNF package manager cache..."
sudo dnf clean all 2>/dev/null || echo "   ⚠ DNF not available or already clean"
sudo rm -rf /var/tmp/dnf-admin-* 2>/dev/null
echo "   ✅ DNF cache cleaned"

# 3. Vacuum journal logs (400+ MB)
echo "3. Vacuuming systemd journal logs..."
sudo journalctl --vacuum-time=7d 2>/dev/null || echo "   ⚠ Journal vacuum skipped"
sudo journalctl --vacuum-size=100M 2>/dev/null || echo "   ⚠ Journal size limit skipped"
# Remove old compressed logs
sudo rm -f /var/log/messages-2026*.gz 2>/dev/null
sudo rm -f /var/log/kern-2026*.gz 2>/dev/null
echo "   ✅ Journal logs cleaned"

echo ""

# Priority 2: Medium Impact Items
echo "🔧 Priority 2: Medium Impact Cleanup"
echo "-------------------------------------"

# 4. Clean user cache
echo "4. Cleaning user cache directories..."
rm -rf /home/admin/.cache/pip 2>/dev/null
rm -rf /home/admin/.cache/npm 2>/dev/null
echo "   ✅ User cache cleaned"

# 5. Remove old backup tarball
echo "5. Removing old backup files..."
OLD_BACKUP="/home/admin/.openclaw/workspace/vmassit-backup-20260510_221323.tar.gz"
if [ -f "$OLD_BACKUP" ]; then
    rm -f "$OLD_BACKUP"
    echo "   ✅ Removed old backup tarball"
else
    echo "   ℹ No old backup tarball found"
fi

# 6. Clean temporary files
echo "6. Cleaning temporary files..."
sudo rm -rf /var/tmp/* 2>/dev/null
find /tmp -type f -mtime +7 -delete 2>/dev/null
echo "   ✅ Temporary files cleaned"

echo ""

# Priority 3: Optional Large Items (Commented out - uncomment if needed)
echo "🔧 Priority 3: Optional Large Cleanup (DISABLED)"
echo "-------------------------------------------------"
echo "⚠ The following items are commented out in the script."
echo "   Uncomment them if you're sure they're not needed:"
echo ""
echo "# DingTalk Connector (880 MB):"
echo "#   rm -rf /home/admin/.openclaw/extensions/dingtalk-connector"
echo ""
echo "# QQBot Extension (676 MB):"
echo "#   rm -rf /home/admin/.openclaw/extensions/openclaw-qqbot"
echo ""
echo "# Linuxbrew (1.5 GB) - ONLY if not using Homebrew packages:"
echo "#   rm -rf /home/linuxbrew/.linuxbrew"
echo ""

# Show final disk usage
echo "=========================================="
echo "✅ Cleanup Complete!"
echo "=========================================="
echo ""
echo "📊 Disk usage after cleanup:"
show_disk_usage

echo "💡 Recommendations:"
echo "   - Monitor disk usage with: df -h /"
echo "   - Check largest directories: du -sh /* 2>/dev/null | sort -rh | head -10"
echo "   - Set up log rotation to prevent future buildup"
echo ""
echo "To free additional ~3 GB, manually remove unused OpenClaw extensions:"
echo "  rm -rf /home/admin/.openclaw/extensions/dingtalk-connector  # 880MB"
echo "  rm -rf /home/admin/.openclaw/extensions/openclaw-qqbot      # 676MB"
echo ""
echo "If Linuxbrew is not needed (~1.5 GB):"
echo "  rm -rf /home/linuxbrew/.linuxbrew"
