#!/bin/bash
# Auto Trade System - VPS Setup Script
# Target: Ubuntu 22.04 LTS
# Purpose: One-command VPS initialization

set -euo pipefail

echo "🚀 Setting up Auto Trade System VPS..."
echo ""

# Step 1: System updates
echo "📦 Updating system packages..."
sudo apt update && sudo apt upgrade -y
echo "✅ System updated"
echo ""

# Step 2: Install prerequisites
echo "📦 Installing prerequisites..."
sudo apt install -y \
    git \
    curl \
    wget \
    ufw \
    fail2ban \
    htop \
    tmux \
    python3-pip \
    build-essential
echo "✅ Prerequisites installed"
echo ""

# Step 3: Install Docker & Docker Compose
echo "🐳 Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker $USER
    echo "✅ Docker installed"
else
    echo "✅ Docker already installed: $(docker --version)"
fi
echo ""

# Step 4: Install Node.js (for Claude Code CLI)
echo "🟢 Installing Node.js..."
if ! command -v node &> /dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt install -y nodejs
    echo "✅ Node.js installed: $(node --version)"
else
    echo "✅ Node.js already installed: $(node --version)"
fi
echo ""

# Step 5: Configure firewall
echo "🔥 Configuring firewall..."
sudo ufw allow 22/tcp
sudo ufw allow 8000/tcp  # FastAPI
sudo ufw allow 3000/tcp  # Grafana
sudo ufw allow 9090/tcp  # Prometheus
sudo ufw --force enable
echo "✅ Firewall configured and enabled"
echo ""

# Step 6: Verify installation
echo "🔍 Verifying installation..."
echo "Docker: $(docker --version)"
echo "Docker Compose: $(docker compose version 2>/dev/null || echo 'Not available')"
echo "Node.js: $(node --version 2>/dev/null || echo 'Not available')"
echo "Git: $(git --version)"
echo ""

echo "✅ VPS base setup complete!"
echo ""
echo "Next steps:"
echo "1. Run: ./scripts/vps/install_tailscale.sh"
echo "2. Follow the authentication URL to connect Tailscale"
echo "3. Run: ./scripts/vps/enable_tailscale_exit_node.sh"
