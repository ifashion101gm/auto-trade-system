#!/bin/bash
# Configure SSH to accept Tailscale connections only (optional security hardening)
# Purpose: Secure SSH access via Tailscale (safer than public SSH)

set -euo pipefail

echo "🔒 Configuring Tailscale SSH..."
echo ""

# Option 1: Keep standard SSH but restrict to Tailscale IPs
echo "Creating SSH configuration to allow Tailscale network..."
sudo mkdir -p /etc/ssh/sshd_config.d
cat << 'EOF' | sudo tee /etc/ssh/sshd_config.d/tailscale.conf
# Allow SSH from Tailscale network only (100.64.0.0/10 is Tailscale CGNAT range)
# Uncomment the line below to restrict to Tailscale IPs only
#AllowUsers *@100.*

# Security hardening
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
EOF

echo "✅ SSH configuration created"
echo ""

# Option 2: Enable Tailscale SSH (beta feature, requires Tailscale admin approval)
# Uncomment the following lines if you want to use Tailscale SSH instead of OpenSSH
# echo "Enabling Tailscale SSH (beta)..."
# sudo tailscale set --ssh
# echo "✅ Tailscale SSH enabled"

# Restart SSH
echo "Restarting SSH service..."
sudo systemctl restart sshd
echo "✅ SSH restarted"
echo ""

echo "✅ SSH configured for Tailscale access"
echo ""
echo "Connect via: ssh admin@<tailscale-ip>"
echo ""
echo "⚠️  IMPORTANT: Make sure you have SSH key-based authentication set up"
echo "   before disabling password authentication!"
echo ""
echo "To test SSH access:"
echo "1. Copy your public key to VPS: ssh-copy-id admin@<tailscale-ip>"
echo "2. Test connection: ssh admin@<tailscale-ip>"
