#!/bin/bash
# Tailscale Installation for VPS
# Purpose: Install and configure Tailscale on VPS

set -euo pipefail

echo "🔐 Installing Tailscale..."
echo ""

# Install Tailscale
if ! command -v tailscale &> /dev/null; then
    echo "📦 Downloading and installing Tailscale..."
    curl -fsSL https://tailscale.com/install.sh | sh
    echo "✅ Tailscale installed"
else
    echo "✅ Tailscale already installed: $(tailscale version)"
fi
echo ""

# Start Tailscale (will provide login URL)
echo "🔑 Starting Tailscale authentication..."
echo ""
sudo tailscale up --advertise-exit-node

echo ""
echo "⚠️  IMPORTANT: Copy the URL above and authenticate in your browser"
echo "   Use same Google/GitHub/Microsoft account as your laptop"
echo ""
echo "After authentication:"
echo "1. Go to https://login.tailscale.com/admin/machines"
echo "2. Approve this VPS as an exit node"
echo "3. Run: ./scripts/vps/enable_tailscale_exit_node.sh"
