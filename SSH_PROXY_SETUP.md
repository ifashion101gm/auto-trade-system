# WireGuard VPN Setup - SSH Connection Issue Solution

## ❌ The Problem

When you activate WireGuard with `AllowedIPs = 0.0.0.0/0`, it routes ALL traffic through the VPN, including your SSH connection back to the VPS. This creates a routing loop:

```
Your Laptop → VPN → VPS → VPN → VPS → VPN... (loop!)
```

Even the split configuration `0.0.0.0/1, 128.0.0.0/1` doesn't work properly on Windows because Windows routing still captures the VPS IP.

## ✅ The Better Solution: SSH SOCKS Proxy

Instead of WireGuard VPN, use an SSH SOCKS proxy. This routes ONLY Claude Code traffic through the VPS while keeping your SSH connection stable.

### Advantages:
- ✅ No IDE disconnection
- ✅ Simpler setup
- ✅ Only routes what you need
- ✅ No routing conflicts
- ✅ Works immediately

---

## Setup Instructions

### Step 1: Create SSH Tunnel

On your **Windows laptop**, open PowerShell and run:

```powershell
ssh -D 1080 -C -N admin@47.84.5.196
```

This creates a SOCKS proxy on `localhost:1080` that tunnels through your VPS.

**Keep this PowerShell window open!**

### Step 2: Configure Claude Code to Use the Proxy

Claude Code respects the `HTTPS_PROXY` environment variable. Before running Claude:

```powershell
# Set proxy for current session
$env:HTTPS_PROXY = "socks5://127.0.0.1:1080"
$env:HTTP_PROXY = "socks5://127.0.0.1:1080"

# Verify proxy is set
echo $env:HTTPS_PROXY

# Now run Claude Code
claude
```

Claude Code will now route all API calls through your VPS!

### Step 3: Verify It Works

Open a **new PowerShell window** and run:

```powershell
# Set proxy
$env:HTTPS_PROXY = "socks5://127.0.0.1:1080"

# Test if traffic goes through VPS
curl.exe -x socks5://127.0.0.1:1080 ifconfig.me
```

You should see `47.84.5.196` (your VPS IP).

---

## Making It Persistent

### Option A: Create a Launch Script

Create a file called `claude-with-proxy.ps1` on your Windows desktop:

```powershell
# Start SSH tunnel in background
Start-Process powershell -ArgumentList "-NoExit", "-Command", "ssh -D 1080 -C -N admin@47.84.5.196"

# Wait for tunnel to establish
Start-Sleep -Seconds 3

# Set proxy environment variables
$env:HTTPS_PROXY = "socks5://127.0.0.1:1080"
$env:HTTP_PROXY = "socks5://127.0.0.1:1080"

Write-Host "Proxy tunnel established on port 1080" -ForegroundColor Green
Write-Host "Claude Code will now use VPS IP for API calls" -ForegroundColor Cyan
Write-Host ""

# Launch Claude Code
claude
```

Just double-click this script to launch Claude with the proxy!

### Option B: Add to Windows Environment Variables

1. Press `Win + R`, type `sysdm.cpl`, press Enter
2. Go to "Advanced" tab → "Environment Variables"
3. Under "User variables", click "New"
4. Add:
   - Variable name: `HTTPS_PROXY`
   - Variable value: `socks5://127.0.0.1:1080`
5. Repeat for `HTTP_PROXY`
6. Restart PowerShell/VS Code

Then you only need to run the SSH tunnel once:

```powershell
ssh -D 1080 -C -N admin@47.84.5.196
```

---

## Testing

### Test 1: Check Proxy is Working

```powershell
# Without proxy
curl.exe ifconfig.me
# Shows: Your local IP

# With proxy
curl.exe -x socks5://127.0.0.1:1080 ifconfig.me
# Shows: 47.84.5.196 (VPS IP)
```

### Test 2: Verify Claude Code Uses Proxy

```powershell
$env:HTTPS_PROXY = "socks5://127.0.0.1:1080"
claude
```

All API calls will use your VPS IP!

---

## Comparison: WireGuard vs SSH Proxy

| Feature | WireGuard VPN | SSH SOCKS Proxy |
|---------|---------------|-----------------|
| SSH Stability | ❌ Breaks IDE connection | ✅ Stays connected |
| Setup Complexity | Complex | Simple |
| Routes All Traffic | Yes | Only apps using proxy |
| Windows Compatibility | Problematic | Works perfectly |
| Performance | Slightly faster | Slightly slower |
| Recommended | ❌ No | ✅ Yes |

---

## Quick Commands Reference

### Start SSH Tunnel

```powershell
# Basic tunnel
ssh -D 1080 -C -N admin@47.84.5.196

# With compression and keep-alive
ssh -D 1080 -C -N -o ServerAliveInterval=60 admin@47.84.5.196
```

### Set Proxy for Current Session

```powershell
$env:HTTPS_PROXY = "socks5://127.0.0.1:1080"
$env:HTTP_PROXY = "socks5://127.0.0.1:1080"
```

### Test Proxy

```powershell
curl.exe -x socks5://127.0.0.1:1080 ifconfig.me
```

### Stop Tunnel

Press `Ctrl+C` in the PowerShell window running the SSH tunnel.

---

## Troubleshooting

### SSH Key Authentication

If you're not using SSH keys yet, set them up:

```powershell
# Generate SSH key (if you don't have one)
ssh-keygen -t ed25519

# Copy to VPS
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh admin@47.84.5.196 "cat >> .ssh/authorized_keys"
```

### Proxy Not Working

1. Check SSH tunnel is running:
   ```powershell
   Test-NetConnection -ComputerName 127.0.0.1 -Port 1080
   ```

2. Verify environment variable:
   ```powershell
   echo $env:HTTPS_PROXY
   # Should show: socks5://127.0.0.1:1080
   ```

3. Test directly:
   ```powershell
   curl.exe -v -x socks5://127.0.0.1:1080 ifconfig.me
   ```

### Windows Firewall

If connection fails, allow SSH through Windows Firewall:
- Port 22 outbound should be allowed (usually is by default)

---

## Summary

**Stop using WireGuard for this use case.** The SSH SOCKS proxy is:
- ✅ Simpler
- ✅ More reliable
- ✅ Doesn't break IDE connection
- ✅ Perfect for routing Claude Code API calls

Just run:
```powershell
ssh -D 1080 -C -N admin@47.84.5.196
```

Then:
```powershell
$env:HTTPS_PROXY = "socks5://127.0.0.1:1080"
claude
```

Done! 🎉
