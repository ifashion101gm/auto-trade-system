# Claude Code Authentication Fix Guide

## Problem
Error in VSCode: "Subprocess initialization did not complete within 60000ms — check authentication and network connectivity"

## Root Cause
Claude Code requires OAuth authentication through a browser flow. The VSCode extension spawns a subprocess that waits for authentication, but times out after 60 seconds if authentication is not completed.

## Solution

### Quick Fix (Recommended)

1. **Open a terminal** (not inside VSCode)
2. **Navigate to workspace**:
   ```bash
   cd /home/admin/.openclaw/workspace/auto-trade-system
   source .venv/bin/activate
   ```
3. **Run the fix script**:
   ```bash
   ./scripts/fix_claude_auth.sh
   ```
4. **Follow the prompts** to authenticate via browser
5. **Restart VSCode completely** (close all windows)
6. **Try Claude Code again** in VSCode

### Manual Authentication

If you prefer to do it manually:

```bash
cd /home/admin/.openclaw/workspace/auto-trade-system
source .venv/bin/activate
claude login
```

A browser window will open. Sign in with your Anthropic account and authorize the application.

### Verify Authentication

After authentication, verify it works:

```bash
claude --version
```

You should see the Claude Code version without errors.

### If Browser Doesn't Open

If you're on a headless server or the browser doesn't open automatically:

1. **Check if you have a display server**:
   ```bash
   echo $DISPLAY
   ```

2. **If using SSH**, enable X11 forwarding:
   ```bash
   ssh -X user@server
   ```

3. **Or use manual token setup** (if available):
   - Visit https://console.anthropic.com/ in a browser
   - Generate an API key
   - Note: Claude Code primarily uses OAuth, not API keys

### Network Issues

If you're behind a corporate firewall or proxy:

1. **Check proxy settings**:
   ```bash
   env | grep -i proxy
   ```

2. **Set proxy if needed**:
   ```bash
   export HTTPS_PROXY=http://your-proxy:port
   export HTTP_PROXY=http://your-proxy:port
   ```

3. **Test connectivity**:
   ```bash
   curl -I https://api.anthropic.com
   ```

### Common Issues

#### Issue 1: "Command not found: claude"
**Solution**: Install Claude Code
```bash
npm install -g @anthropic-ai/claude-code
```

#### Issue 2: Authentication keeps timing out
**Solution**: 
- Ensure you have a working browser
- Check firewall settings
- Try from a different network
- Use `--timeout` flag if available

#### Issue 3: VSCode still shows error after authentication
**Solution**:
- Completely close VSCode (not just the window)
- Kill any running Claude processes:
  ```bash
  pkill -f claude
  ```
- Restart VSCode

#### Issue 4: OAuth callback fails
**Solution**:
- Check if port 8085 is available (default OAuth callback port)
- Try running `claude login` with admin privileges if needed

### Environment Variables

Claude Code may use these environment variables:

```bash
# Optional: Set custom OAuth callback port
export CLAUDE_OAUTH_PORT=8085

# Optional: Enable debug logging
export CLAUDE_DEBUG=true

# Optional: Custom config directory
export CLAUDE_CONFIG_DIR=~/.claude
```

### Verification Checklist

- [ ] Claude Code installed (`claude --version`)
- [ ] Authentication completed (`~/.claude` directory exists with credentials)
- [ ] Network connectivity to `api.anthropic.com` works
- [ ] No firewall blocking OAuth callback
- [ ] VSCode restarted after authentication
- [ ] Claude Code extension updated to latest version

### Additional Resources

- [Claude Code Documentation](https://docs.anthropic.com/claude-code)
- [Anthropic Console](https://console.anthropic.com/)
- [Claude Code GitHub](https://github.com/anthropics/claude-code)

---

**Last Updated**: May 18, 2026  
**Workspace**: `/home/admin/.openclaw/workspace/auto-trade-system`
