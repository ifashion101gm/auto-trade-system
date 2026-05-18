# Claude Code Launcher with SOCKS5 Proxy
# This script starts an SSH tunnel and launches Claude Code through the proxy

param(
    [string]$VPS_IP = "47.84.5.196",
    [string]$VPS_User = "admin",
    [int]$ProxyPort = 1080
)

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Claude Code with VPS Proxy Launcher" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check if Claude Code is installed
Write-Host "Step 1: Checking Claude Code installation..." -ForegroundColor Yellow

# Known Claude Code location on this system
$claudeExe = "C:\Users\aungp\AppData\Local\AnthropicClaude\claude.exe"

if (Test-Path $claudeExe) {
    $claudeCmd = $claudeExe
    Write-Host "✓ Found Claude Code at: $claudeCmd" -ForegroundColor Green
} else {
    # Try to find Claude Code in common locations
    $claudePaths = @(
        "$env:APPDATA\npm\claude.cmd",
        "$env:APPDATA\npm\node_modules\.bin\claude.cmd",
        "claude"
    )
    
    foreach ($path in $claudePaths) {
        try {
            $cmd = Get-Command $path -ErrorAction Stop
            $claudeCmd = $cmd.Source
            Write-Host "✓ Found Claude Code at: $claudeCmd" -ForegroundColor Green
            break
        } catch {
            continue
        }
    }
}

if (-not $claudeCmd) {
    Write-Host "✗ Claude Code not found!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Expected location: C:\Users\aungp\AppData\Local\AnthropicClaude\claude.exe" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Please verify the installation or provide the correct path:" -ForegroundColor Yellow
    Write-Host "  .\launch-claude-proxy.ps1 -ClaudePath 'C:\path\to\claude.exe'" -ForegroundColor Cyan
    exit 1
}

# Step 2: Start SSH tunnel
Write-Host ""
Write-Host "Step 2: Starting SSH tunnel to $VPS_IP..." -ForegroundColor Yellow

# Check if tunnel is already running
$tunnelCheck = Get-NetTCPConnection -LocalPort $ProxyPort -ErrorAction SilentlyContinue
if ($tunnelCheck) {
    Write-Host "⚠ Port $ProxyPort is already in use" -ForegroundColor Yellow
    Write-Host "  Tunnel might already be running" -ForegroundColor Gray
    $useExisting = Read-Host "Use existing tunnel? (Y/n)"
    if ($useExisting -ne 'n' -and $useExisting -ne 'N') {
        Write-Host "✓ Using existing tunnel" -ForegroundColor Green
    } else {
        Write-Host "  Please close the existing tunnel first" -ForegroundColor Yellow
        Write-Host "  Or run with different port: .\launch-claude-proxy.ps1 -ProxyPort 1081" -ForegroundColor Gray
        exit 1
    }
} else {
    Write-Host "  Opening new PowerShell window for SSH tunnel..." -ForegroundColor Gray
    Write-Host "  Keep that window open while using Claude Code!" -ForegroundColor Yellow
    Write-Host ""
    
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "Write-Host 'SSH Tunnel Window - Keep Open!' -ForegroundColor Green; ssh -D $ProxyPort -C -N ${VPS_User}@${VPS_IP}"
    
    Write-Host "  Waiting for tunnel to establish..." -ForegroundColor Gray
    Start-Sleep -Seconds 3
    
    # Verify tunnel is running
    $tunnelCheck = Get-NetTCPConnection -LocalPort $ProxyPort -ErrorAction SilentlyContinue
    if ($tunnelCheck) {
        Write-Host "✓ SSH tunnel established on port $ProxyPort" -ForegroundColor Green
    } else {
        Write-Host "⚠ Could not verify tunnel on port $ProxyPort" -ForegroundColor Yellow
        Write-Host "  Check the SSH tunnel window for errors" -ForegroundColor Gray
        Write-Host "  Continuing anyway..." -ForegroundColor Yellow
    }
}

# Step 3: Set proxy environment variables
Write-Host ""
Write-Host "Step 3: Configuring proxy..." -ForegroundColor Yellow

$env:HTTPS_PROXY = "socks5://127.0.0.1:$ProxyPort"
$env:HTTP_PROXY = "socks5://127.0.0.1:$ProxyPort"
$env:NO_PROXY = "localhost,127.0.0.1"

Write-Host "✓ HTTPS_PROXY = $env:HTTPS_PROXY" -ForegroundColor Green
Write-Host "✓ HTTP_PROXY = $env:HTTP_PROXY" -ForegroundColor Green

# Step 4: Verify proxy is working
Write-Host ""
Write-Host "Step 4: Verifying proxy connection..." -ForegroundColor Yellow

try {
    $testResult = curl.exe -s --max-time 5 -x "socks5://127.0.0.1:$ProxyPort" ifconfig.me 2>$null
    if ($testResult) {
        Write-Host "✓ Public IP through proxy: $testResult" -ForegroundColor Cyan
        if ($testResult.Trim() -eq $VPS_IP) {
            Write-Host "✓ Traffic is routing through VPS!" -ForegroundColor Green
        } else {
            Write-Host "⚠ IP differs from VPS (might be CDN/proxy)" -ForegroundColor Yellow
        }
    } else {
        Write-Host " Could not verify proxy" -ForegroundColor Yellow
    }
} catch {
    Write-Host "⚠ Proxy verification failed" -ForegroundColor Yellow
    Write-Host "  Claude Code may not use the proxy correctly" -ForegroundColor Gray
}

# Step 5: Launch Claude Code
Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Launching Claude Code" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "✓ SSH Tunnel: Active on port $ProxyPort" -ForegroundColor Green
Write-Host "✓ Proxy: socks5://127.0.0.1:$ProxyPort" -ForegroundColor Green
Write-Host "✓ VPS IP: $VPS_IP" -ForegroundColor Green
Write-Host "✓ Claude: $claudeCmd" -ForegroundColor Green
Write-Host ""
Write-Host "IMPORTANT: Keep the SSH tunnel window open!" -ForegroundColor Yellow
Write-Host ""

# Launch Claude Code
& $claudeCmd

# Cleanup when Claude exits
Write-Host ""
Write-Host "Claude Code closed." -ForegroundColor Yellow
Write-Host "Cleaning up environment variables..." -ForegroundColor Gray

Remove-Item Env:HTTPS_PROXY -ErrorAction SilentlyContinue
Remove-Item Env:HTTP_PROXY -ErrorAction SilentlyContinue

Write-Host "✓ Cleanup complete" -ForegroundColor Green
Write-Host ""
Write-Host "You can close the SSH tunnel window now (Ctrl+C)" -ForegroundColor Gray
Write-Host "Or keep it open for next time" -ForegroundColor Gray
