# VPS Storage Cleanup Summary

## Current Status
- **Total Disk Space**: 40 GB
- **Used**: 29 GB (76%)
- **Available**: 9 GB (24%)

## Storage Analysis

### Major Storage Consumers

| Location | Size | Description |
|----------|------|-------------|
| `/usr/lib` | 4.0 GB | System libraries (KEEP) |
| `/home/admin/.openclaw/extensions` | **1.6 GB** | OpenClaw extensions |
| `/home/linuxbrew/.linuxbrew` | **1.5 GB** | Linuxbrew package manager |
| `/usr/local` | 1.6 GB | Local installations (KEEP) |
| `/usr/src/Python-3.11.0` | **448 MB** | Python source code (SAFE TO REMOVE) |
| `/var/log/journal` | **545 MB** | Systemd journal logs (CAN BE REDUCED) |
| `/var/tmp/dnf-admin-*` | **201 MB** | DNF cache (SAFE TO REMOVE) |
| `/home/admin/.cache` | 162 MB | User cache (CAN BE CLEANED) |
| `/home/admin/.local` | 178 MB | Local user data |
| `auto-trade-system/.venv` | 282 MB | Trading system venv (KEEP) |

## Cleanup Actions Performed

### ✅ Completed (Within Sandbox Limits)
1. **Pip cache purge**: Freed 201.6 MB (755 files)
2. **Python __pycache__ cleanup**: Removed compiled bytecode outside .venv
3. **Temporary extraction files**: Cleaned /tmp/docx_extract

### 📝 Manual Actions Required (Outside Sandbox)

Run the provided script: `bash cleanup_vps_storage.sh`

This will safely remove:

#### Priority 1: High Impact (~1.2 GB)
1. **Python 3.11 source code**: 448 MB
   - Already compiled and installed, source not needed
   
2. **DNF package cache**: 201 MB
   - Package manager temporary files
   
3. **Systemd journal logs**: ~400-500 MB
   - Vacuumed to 7 days / 100 MB max
   - Old compressed logs removed

#### Priority 2: Medium Impact (~300 MB)
4. **User cache directories**: ~162 MB
   - Pip, npm, and other application caches
   
5. **Old backup tarball**: 102 MB
   - vmassit-backup-20260510_221323.tar.gz
   
6. **Temporary files**: Variable
   - /var/tmp and old /tmp files

#### Priority 3: Optional Large Items (~3+ GB)
*These are commented out in the script - uncomment if safe to remove:*

7. **DingTalk Connector extension**: 880 MB
   - Only if not using DingTalk integration
   
8. **QQBot extension**: 676 MB
   - Only if not using QQ Bot integration
   
9. **Linuxbrew**: 1.5 GB
   - ONLY if you don't use Homebrew packages
   - Check first: `brew list`

## Expected Results

### After Priority 1 & 2 (Safe):
- **Freed**: ~1.5 GB
- **New Available**: ~10.5 GB (26%)
- **Risk**: None - all safe operations

### After Priority 3 (Optional):
- **Additional Freed**: ~3 GB
- **New Available**: ~13.5 GB (34%)
- **Risk**: Low - verify extensions not in use first

## Files Created

1. **cleanup_vps_storage.sh** - Automated cleanup script
   - Run with: `bash cleanup_vps_storage.sh`
   - Reviews disk usage before/after
   - Safe defaults with optional items commented out

## Monitoring Commands

```bash
# Check current disk usage
df -h /

# Find largest directories
du -sh /* 2>/dev/null | sort -rh | head -10

# Check home directory usage
du -sh /home/admin/* 2>/dev/null | sort -rh

# Monitor over time
watch -n 60 'df -h /'
```

## Recommendations

1. **Run the cleanup script** immediately for safe 1.5 GB recovery
2. **Review OpenClaw extensions** - remove unused ones for additional 1.5 GB
3. **Evaluate Linuxbrew** - if not actively used, remove for 1.5 GB more
4. **Set up log rotation** to prevent future buildup:
   ```bash
   sudo systemctl enable --now systemd-journald.service
   ```
5. **Schedule regular cleanup** with cron:
   ```bash
   # Monthly cleanup
   0 3 1 * * /path/to/cleanup_vps_storage.sh >> /var/log/cleanup.log 2>&1
   ```

## Safety Notes

✅ **Safe to Remove**:
- Python source code (already compiled)
- Package manager caches
- Old logs and temp files
- Unused extensions

⚠️ **Verify Before Removing**:
- OpenClaw extensions (check if in use)
- Linuxbrew (check `brew list`)

❌ **DO NOT Remove**:
- `/usr/lib`, `/usr/bin` - System files
- `/home/admin/.openclaw/workspace/auto-trade-system` - Trading system
- Active systemd services
- Current database files

## Next Steps

1. Execute: `bash cleanup_vps_storage.sh`
2. Review output and verify disk space freed
3. Decide on Priority 3 items (extensions/Linuxbrew)
4. Set up monitoring to prevent future storage issues
