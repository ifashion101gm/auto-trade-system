# Claude Code Fix - Quick Reference

## ✅ Status: FIXED

The "Subprocess initialization did not complete within 60000ms" error has been resolved.

## What Was Done

1. ✅ Killed stale Claude processes that were blocking initialization
2. ✅ Created wrapper script with `CLAUDE_DEBUG=true` 
3. ✅ Configured VSCode to use the wrapper
4. ✅ Added environment variable to `.bashrc`

## Files Created/Modified

- **Wrapper Script**: `/home/admin/.openclaw/workspace/auto-trade-system/claude-wrapper.sh`
- **VSCode Settings**: `/home/admin/.openclaw/workspace/auto-trade-system/.vscode/settings.json`
- **Shell Profile**: `~/.bashrc` (added `export CLAUDE_DEBUG=true`)

## How to Use Claude Code Now

### Option 1: Via VSCode (Recommended)
1. Close all VSCode windows
2. Reopen VSCode
3. Open your workspace
4. Claude Code should work automatically

### Option 2: Via Terminal
```bash
source ~/.bashrc  # Load environment variable
claude            # Start Claude Code
```

## If It Stops Working

### Quick Fix
```bash
# Kill stale processes
pkill -9 -f claude

# Test wrapper
timeout 5 /home/admin/.openclaw/workspace/auto-trade-system/claude-wrapper.sh --version

# Restart VSCode
```

### Check Status
```bash
# Verify no stale processes
ps aux | grep "[c]laude"

# Test network
curl -I https://api.anthropic.com

# Check credentials
cat ~/.claude/.credentials.json | python3 -m json.tool | grep expiresAt
```

## Key Commands

```bash
# Kill all Claude processes
pkill -9 -f claude

# Test Claude directly
env CLAUDE_DEBUG=true claude --version

# Test wrapper
/home/admin/.openclaw/workspace/auto-trade-system/claude-wrapper.sh --version

# View Claude logs
ls -lt ~/.claude/sessions/ | head -5

# Check VSCode output
# View → Output → Select "Claude Code"
```

## Root Cause

Claude Code was hanging during initialization because:
1. Stale processes from previous sessions were holding locks
2. Non-debug mode initialization was timing out (likely telemetry/analytics)
3. The 60-second timeout was being hit before completion

**Solution**: Always use `CLAUDE_DEBUG=true` and kill stale processes before starting.

---

**Last Updated**: May 18, 2026  
**Workspace**: `/home/admin/.openclaw/workspace/auto-trade-system`
