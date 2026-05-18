#!/bin/bash
# Enable Tailscale Exit Node
# Purpose: Enable and verify Tailscale exit node

set -euo pipefail

echo "🌐 Enabling Tailscale exit node..."
echo ""

# Re-run with exit node flag
sudo tailscale up --advertise-exit-node --reset

# Get Tailscale IP
TAILSCALE_IP=$(tailscale ip -4)
echo "✅ Tailscale IP: $TAILSCALE_IP"
echo ""

# Verify status
echo "📊 Tailscale Status:"
tailscale status
echo ""

echo "📋 Next steps:"
echo "1. On laptop: Open Tailscale app → Settings → Exit Nodes → Select this VPS"
echo "2. Verify: Visit https://whatismyipaddress.com (should show Singapore IP)"
echo "3. For SSH: ssh admin@$TAILSCALE_IP"
echo ""
echo "💡 Tip: You can now access all services via Tailscale IP:"
echo "   - Grafana: http://$TAILSCALE_IP:3000"
echo "   - API Docs: http://$TAILSCALE_IP:8000/docs"
echo "   - Prometheus: http://$TAILSCALE_IP:9090"
