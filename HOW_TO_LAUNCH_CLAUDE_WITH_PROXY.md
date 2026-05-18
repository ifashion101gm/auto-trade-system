# How to Launch Claude Code with VPS Proxy

## Quick Setup (3 Steps)

### Step 1: Copy the Launcher Script to Windows

Copy the content of `launch-claude-proxy.ps1` from your VPS and save it on your Windows machine:

**Save to:** `C:\Users\aungp\Downloads\launch-claude-proxy.ps1`

### Step 2: Run the Script

Open PowerShell and run:

```powershell
# Navigate to Downloads
cd C:\Users\aungp\Downloads

# Allow script execution (first time only)
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# Run the launcher
.\launch-claude-proxy.ps1
```

### Step 3: That's It!

The script will automatically:
1. ✅ Find Claude Code at: `C:\Users\aungp\AppData\Local\AnthropicClaude\claude.exe`
2. ✅ Start SSH tunnel to VPS (47.84.5.196)
3. ✅ Configure SOCKS5 proxy on port 1080
4. ✅ Verify proxy is working
5. ✅ Launch Claude Code

All Claude Code API calls will now use your VPS IP!

---

## What You'll See

When you run the script, you'll see:

```
=========================================
Claude Code with VPS Proxy Launcher
=========================================

Step 1: Checking Claude Code installation...
✓ Found Claude Code at: C:\Users\aungp\AppData\Local\AnthropicClaude\claude.exe

Step 2: Starting SSH tunnel to 47.84.5.196...
  Opening new PowerShell window for SSH tunnel...
  Keep that window open while using Claude Code!

  Waiting for tunnel to establish...
✓ SSH tunnel established on port 1080

Step 3: Configuring proxy...
✓ HTTPS_PROXY = socks5://127.0.0.1:1080
✓ HTTP_PROXY = socks5://127.0.0.1:1080

Step 4: Verifying proxy connection...
✓ Public IP through proxy: 47.84.5.196
✓ Traffic is routing through VPS!

=========================================
Launching Claude Code
=========================================

✓ SSH Tunnel: Active on port 1080
✓ Proxy: socks5://127.0.0.1:1080
✓ VPS IP: 47.84.5.196
✓ Claude: C:\Users\aungp\AppData\Local\AnthropicClaude\claude.exe

IMPORTANT: Keep the SSH tunnel window open!
```

---

## Manual Method (If Script Doesn't Work)

If you prefer to do it manually:

```powershell
# Step 1: Start SSH tunnel in one window
ssh -D 1080 -C -N admin@47.84.5.196

# Step 2: In NEW window, set proxy and launch Claude
$env:HTTPS_PROXY = "socks5://127.0.0.1:1080"
$env:HTTP_PROXY = "socks5://127.0.0.1:1080"
& "C:\Users\aungp\AppData\Local\AnthropicClaude\claude.exe"
```

---

## Verification

After Claude launches, you can verify it's using the VPS IP:

```powershell
# In a separate PowerShell window
curl.exe -x socks5://127.0.0.1:1080 ifconfig.me
# Should show: 47.84.5.196
```

---

## Important Notes

- ✅ **Keep the SSH tunnel window open** while using Claude Code
- ✅ When you close Claude, the proxy environment variables are automatically cleaned up
- ✅ You can reuse the SSH tunnel for future Claude sessions (just don't close the tunnel window)
- ✅ Your IDE SSH connection remains stable (no WireGuard issues!)

---

## Troubleshooting

### "Script not recognized" error

Run this first:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### "Claude.exe not found"

Verify the file exists:
```powershell
Test-Path "C:\Users\aungp\AppData\Local\AnthropicClaude\claude.exe"
```

Should return: `True`

### "SSH connection refused"

Check your SSH keys are set up:
```powershell
ssh admin@47.84.5.196
```

If it works, the tunnel will work too.

### Port 1080 already in use

Another application is using port 1080. Either:
- Close the other application, OR
- Use a different port: `.\launch-claude-proxy.ps1 -ProxyPort 1081`

---

## Comparison: This vs WireGuard VPN

| Feature | SSH Proxy | WireGuard VPN |
|---------|-----------|---------------|
| SSH Stable | ✅ Yes | ❌ Breaks IDE |
| DNS Works | ✅ Yes | ️ Fails |
| Setup | ✅ Simple | Complex |
| Claude Proxy | ✅ Automatic | Manual |
| Windows Support | ✅ Perfect | Problematic |

**Winner: SSH SOCKS Proxy** 🎉

---

## Files Reference

- `launch-claude-proxy.ps1` - The launcher script (updated with your Claude path)
- `SSH_PROXY_SETUP.md` - Complete SOCKS proxy documentation
- `client_windows.conf` - WireGuard config (no longer needed)

---

**Ready to go!** Just copy the script to your Windows machine and run it. 🚀
