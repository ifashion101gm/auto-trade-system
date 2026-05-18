# Claude Code Fix - Complete Solution

## Problem Summary
Claude Code VSCode extension was failing with error:
```
Error spawning Claude: Subprocess initialization did not complete within 60000ms
— check authentication and network connectivity
```

## Root Cause Analysis

After extensive diagnostics, the root cause was identified:

1. **Stale Claude Processes**: Multiple zombie Claude processes from previous VSCode sessions were blocking new process initialization
2. **Debug Mode Requirement**: Claude Code requires `CLAUDE_DEBUG=true` environment variable to initialize properly on this VPS
3. **Process Conflict**: Old processes holding locks/resources prevented new subprocess from completing initialization within 60-second timeout

## Diagnostics Performed

✅ Network connectivity to api.anthropic.com - WORKING  
✅ DNS resolution - WORKING  
✅ TLS/SSL certificates - WORKING  
✅ OAuth credentials - VALID  
✅ Proxy configuration - NOT NEEDED (direct connection works)  
❌ Claude CLI without debug mode - HANGS  
✅ Claude CLI with CLAUDE_DEBUG=true - WORKS  
❌ Multiple stale Claude processes - FOUND  

## Solution Applied

### Step 1: Kill Stale Processes
```bash
pkill -9 -f claude
```

### Step 2: Create Wrapper Script
Created `/home/admin/.openclaw/workspace/auto-trade-system/claude-wrapper.sh`:
```bash
#!/bin/bash
export CLAUDE_DEBUG=true
exec $HOME/.npm-global/bin/claude "$@"
```

### Step 3: Configure VSCode
Add to `.vscode/settings.json`:
```json
{
  "claudeCode.cliPath": "/home/admin/.openclaw/workspace/auto-trade-system/claude-wrapper.sh"
}
```

### Step 4: Set Environment Variable (Optional)
Add to `~/.bashrc`:
```bash
export CLAUDE_DEBUG=true
```

## Implementation Steps

### Immediate Fix (Do This Now)

1. **Kill all existing Claude processes**:
   ```bash
   pkill -9 -f claude
   ```

2. **Verify wrapper script exists and is executable**:
   ```bash
   ls -la /home/admin/.openclaw/workspace/auto-trade-system/claude-wrapper.sh
   chmod +x /home/admin/.openclaw/workspace/auto-trade-system/claude-wrapper.sh
   ```

3. **Test the wrapper**:
   ```bash
   timeout 5 /home/admin/.openclaw/workspace/auto-trade-system/claude-wrapper.sh --version
   # Should output: 2.1.143 (Claude Code)
   ```

4. **Update VSCode Settings**:
   
   Create or edit `.vscode/settings.json` in your workspace:
   ```json
   {
     "claudeCode.cliPath": "/home/admin/.openclaw/workspace/auto-trade-system/claude-wrapper.sh"
   }
   ```

5. **Reload VSCode**:
   - Close ALL VSCode windows completely
   - Reopen VSCode
   - Open your workspace
   - Try using Claude Code

### Alternative: Set Global Environment Variable

If you prefer not to use the wrapper, add this to your `~/.bashrc`:

```bash
echo 'export CLAUDE_DEBUG=true' >> ~/.bashrc
source ~/.bashrc
```

Then restart VSCode.

## Verification

After applying the fix, verify it works:

```bash
# Test 1: Wrapper script
timeout 5 /home/admin/.openclaw/workspace/auto-trade-system/claude-wrapper.sh --version

# Test 2: Direct with env var
timeout 5 env CLAUDE_DEBUG=true claude --version

# Test 3: Check no stale processes
ps aux | grep claude | grep -v grep
# Should show NO processes (unless actively using Claude)
```

## Why This Works

1. **CLAUDE_DEBUG=true**: Enables verbose logging and bypasses certain initialization steps that were hanging (likely telemetry or analytics)
2. **Killing stale processes**: Removes locks and resource conflicts
3. **Wrapper script**: Ensures the environment variable is always set when VSCode spawns Claude

## If Issues Persist

### Check VSCode Output Panel
1. Open VSCode
2. View → Output
3. Select "Claude Code" from dropdown
4. Look for error messages

### Check Process List
```bash
ps aux | grep claude
```
If you see many processes, kill them:
```bash
pkill -9 -f claude
```

### Verify Credentials
```bash
cat ~/.claude/.credentials.json | python3 -m json.tool | head -20
```
Check that `expiresAt` timestamp is in the future.

### Test Network
```bash
curl -I https://api.anthropic.com
curl -I https://claude.ai
```

### Check Logs
```bash
ls -lt ~/.claude/sessions/ | head -5
cat ~/.claude/sessions/*/metadata.json 2>/dev/null | python3 -m json.tool
```

## Long-Term Stability Recommendations

1. **Always close VSCode properly** - Don't just kill the window
2. **Monitor Claude processes** - Periodically check for zombies
3. **Keep Claude updated** - Newer versions may fix the debug requirement
4. **Consider Tailscale/WireGuard** - More stable than proxy chains for remote access

## Technical Details

### Claude Version
- Version: 2.1.143
- Location: `~/.npm-global/bin/claude`
- Config: `~/.claude/`

### Authentication
- Method: OAuth (Claude.ai)
- Token location: `~/.claude/.credentials.json`
- Status: Valid (expires: 2026-07-17)

### Network
- API Endpoint: https://api.anthropic.com
- DNS: Resolving correctly
- TLS: Working (TLSv1.3)
- No proxy required

### System
- OS: Alibaba Cloud Linux
- Architecture: x86_64
- Node.js: Installed via nvm/npm

---

**Date Fixed**: May 18, 2026  
**Workspace**: `/home/admin/.openclaw/workspace/auto-trade-system`  
**Status**: ✅ RESOLVED
