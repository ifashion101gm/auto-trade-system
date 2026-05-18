# WireGuard VPN Connection Script with SSH Protection
# This script activates WireGuard VPN while keeping SSH connection to VPS alive

param(
    [string]$VPS_IP = "47.84.5.196",
    [string]$TunnelName = "client_windows"
)

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "WireGuard VPN Connection with SSH Protection" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

# Check if running as Administrator
if (-NOT ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Host "⚠ This script requires Administrator privileges" -ForegroundColor Yellow
    Write-Host "Please run PowerShell as Administrator and try again" -ForegroundColor Yellow
    exit 1
}

Write-Host "VPS IP: $VPS_IP" -ForegroundColor Gray
Write-Host ""

# Step 1: Check WireGuard status
Write-Host "Step 1: Checking WireGuard status..." -ForegroundColor Yellow
$wgService = Get-Service "WireGuard" -ErrorAction SilentlyContinue

if ($wgService) {
    Write-Host "✓ WireGuard service found" -ForegroundColor Green
} else {
    Write-Host "✗ WireGuard not installed!" -ForegroundColor Red
    Write-Host "Download from: https://www.wireguard.com/install/" -ForegroundColor Yellow
    exit 1
}

# Step 2: Get current default gateway before VPN
Write-Host ""
Write-Host "Step 2: Capturing current network configuration..." -ForegroundColor Yellow

$currentRoutes = Get-NetRoute -DestinationPrefix "0.0.0.0/0" | Where-Object {
    $_.NextHop -ne "0.0.0.0" -and $_.InterfaceAlias -notlike "*WireGuard*"
}

if ($currentRoutes) {
    $defaultGateway = $currentRoutes[0].NextHop
    $defaultInterface = $currentRoutes[0].InterfaceAlias
    Write-Host "✓ Default gateway: $defaultGateway" -ForegroundColor Green
    Write-Host "✓ Interface: $defaultInterface" -ForegroundColor Green
} else {
    Write-Host " Could not detect default gateway" -ForegroundColor Yellow
    Write-Host "Attempting automatic detection..." -ForegroundColor Gray
    $defaultInterface = (Get-NetAdapter | Where-Object { $_.Status -eq 'Up' -and $_.InterfaceAlias -notlike '*WireGuard*' }).InterfaceAlias | Select-Object -First 1
    if ($defaultInterface) {
        $defaultGateway = (Get-NetIPConfiguration -InterfaceAlias $defaultInterface).IPv4DefaultGateway.NextHop
        Write-Host "✓ Detected interface: $defaultInterface" -ForegroundColor Green
    } else {
        Write-Host " Could not find active network interface" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "IMPORTANT INSTRUCTIONS:" -ForegroundColor Yellow
Write-Host "=========================" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. Open WireGuard GUI (if not already open)" -ForegroundColor Cyan
Write-Host "2. Import the file: client_windows.conf" -ForegroundColor Cyan
Write-Host "   Location: $PSScriptRoot\client_windows.conf" -ForegroundColor Gray
Write-Host "3. Click 'Activate' on the tunnel" -ForegroundColor Cyan
Write-Host "4. Come back here and press Enter to continue..." -ForegroundColor Cyan
Write-Host ""
Write-Host "⚠ DO NOT close this window!" -ForegroundColor Red
Write-Host ""

Read-Host "Press Enter after activating the VPN tunnel"

# Step 3: Wait for VPN to stabilize
Write-Host ""
Write-Host "Step 3: Stabilizing VPN connection..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

# Step 4: Add route exclusion for VPS IP
Write-Host ""
Write-Host "Step 4: Adding SSH route protection..." -ForegroundColor Yellow

# Remove any existing specific routes to VPS
$existingVpsRoutes = Get-NetRoute -DestinationPrefix "$VPS_IP/32" -ErrorAction SilentlyContinue
if ($existingVpsRoutes) {
    Write-Host "Removing existing VPS routes..." -ForegroundColor Gray
    $existingVpsRoutes | Remove-NetRoute -Confirm:$false -ErrorAction SilentlyContinue
}

# Add high-priority route for VPS (bypasses VPN)
try {
    New-NetRoute -DestinationPrefix "$VPS_IP/32" `
        -InterfaceAlias $defaultInterface `
        -NextHop $defaultGateway `
        -RouteMetric 1 `
        -ErrorAction Stop | Out-Null
    
    Write-Host "✓ Route added: VPS ($VPS_IP) will use direct connection" -ForegroundColor Green
    Write-Host "✓ Route Metric: 1 (highest priority)" -ForegroundColor Green
} catch {
    Write-Host "✗ Failed to add route: $_" -ForegroundColor Red
    Write-Host "Continuing anyway..." -ForegroundColor Yellow
}

# Step 5: Verify configuration
Write-Host ""
Write-Host "Step 5: Verifying configuration..." -ForegroundColor Yellow
Write-Host ""

# Check route table
Write-Host "Route to VPS ($VPS_IP):" -ForegroundColor Gray
$vpsRoute = Get-NetRoute -DestinationPrefix "$VPS_IP/32" -ErrorAction SilentlyContinue
if ($vpsRoute) {
    Write-Host "✓ Specific route exists for VPS" -ForegroundColor Green
    Write-Host "  Interface: $($vpsRoute.InterfaceAlias)" -ForegroundColor Gray
    Write-Host "  Next Hop: $($vpsRoute.NextHop)" -ForegroundColor Gray
    Write-Host "  Metric: $($vpsRoute.RouteMetric)" -ForegroundColor Gray
} else {
    Write-Host "⚠ No specific route found for VPS" -ForegroundColor Yellow
}

Write-Host ""

# Test SSH connectivity
Write-Host "Testing SSH connectivity to VPS..." -ForegroundColor Gray
try {
    $sshTest = Test-NetConnection -ComputerName $VPS_IP -Port 22 -WarningAction SilentlyContinue -InformationLevel Quiet
    if ($sshTest) {
        Write-Host "✓ SSH port 22 is reachable on $VPS_IP" -ForegroundColor Green
    } else {
        Write-Host "⚠ SSH port test inconclusive" -ForegroundColor Yellow
    }
} catch {
    Write-Host "⚠ Could not test SSH connection" -ForegroundColor Yellow
}

Write-Host ""

# Test general internet through VPN
Write-Host "Testing internet connectivity through VPN..." -ForegroundColor Gray
try {
    $publicIP = (Invoke-RestMethod -Uri "http://ifconfig.me" -TimeoutSec 5 -ErrorAction Stop).Trim()
    Write-Host "Current Public IP: $publicIP" -ForegroundColor Cyan
    
    if ($publicIP -eq $VPS_IP) {
        Write-Host "✓ Traffic is routing through VPS!" -ForegroundColor Green
    } else {
        Write-Host " Current IP ($publicIP) is not VPS IP ($VPS_IP)" -ForegroundColor Yellow
        Write-Host "  This might be expected depending on your network setup" -ForegroundColor Gray
    }
} catch {
    Write-Host "⚠ Could not check public IP (VPN might not be active yet)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "✓ Your SSH connection to VPS is protected" -ForegroundColor Green
Write-Host "✓ All other traffic routes through VPN" -ForegroundColor Green
Write-Host ""
Write-Host "To test Claude Code:" -ForegroundColor Yellow
Write-Host "  Run: claude" -ForegroundColor Gray
Write-Host ""
Write-Host "To disconnect VPN later:" -ForegroundColor Yellow
Write-Host "  1. Open WireGuard GUI" -ForegroundColor Gray
Write-Host "  2. Click 'Deactivate'" -ForegroundColor Gray
Write-Host "  3. The route will be automatically cleaned up" -ForegroundColor Gray
Write-Host ""
Write-Host "⚠ Keep this PowerShell window open!" -ForegroundColor Red
Write-Host "  Closing it will remove the SSH protection route" -ForegroundColor Red
Write-Host ""

# Keep script running to maintain route
Write-Host "Monitoring connection... (Press Ctrl+C to exit and cleanup)" -ForegroundColor Gray
Write-Host ""

try {
    while ($true) {
        Start-Sleep -Seconds 30
        
        # Verify route still exists
        $routeCheck = Get-NetRoute -DestinationPrefix "$VPS_IP/32" -ErrorAction SilentlyContinue
        if (-not $routeCheck) {
            Write-Host "$(Get-Date -Format 'HH:mm:ss') - ⚠ Route missing! Re-adding..." -ForegroundColor Yellow
            New-NetRoute -DestinationPrefix "$VPS_IP/32" `
                -InterfaceAlias $defaultInterface `
                -NextHop $defaultGateway `
                -RouteMetric 1 `
                -ErrorAction SilentlyContinue | Out-Null
            Write-Host "$(Get-Date -Format 'HH:mm:ss') - ✓ Route restored" -ForegroundColor Green
        }
    }
} finally {
    Write-Host ""
    Write-Host "Cleaning up routes..." -ForegroundColor Yellow
    Get-NetRoute -DestinationPrefix "$VPS_IP/32" -ErrorAction SilentlyContinue | 
        Remove-NetRoute -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "✓ Cleanup complete" -ForegroundColor Green
}
