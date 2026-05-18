#!/bin/bash
# Deploy Auto Trade System to VPS
# Purpose: Deploy auto-trade-system to VPS with one command

set -euo pipefail

VPS_IP=${1:-$(tailscale ip -4 2>/dev/null || echo "")}
DEPLOY_DIR="/opt/auto-trade-system"
REPO_URL=${REPO_URL:-"https://github.com/your-repo/auto-trade-system.git"}

if [ -z "$VPS_IP" ]; then
    echo "❌ Error: VPS IP not provided and Tailscale not configured"
    echo "Usage: $0 <vps-ip>"
    echo "   or: Set up Tailscale first"
    exit 1
fi

echo "🚀 Deploying to VPS: $VPS_IP"
echo ""

# Step 1: Clone repository on VPS
echo "📦 Cloning/updating repository on VPS..."
ssh admin@$VPS_IP << EOF
    mkdir -p $DEPLOY_DIR
    cd $DEPLOY_DIR
    
    # Clone or pull latest
    if [ -d ".git" ]; then
        echo "Pulling latest changes..."
        git pull origin main
    else
        echo "Cloning repository..."
        git clone $REPO_URL .
    fi
EOF

echo "✅ Repository updated"
echo ""

# Step 2: Copy environment file securely
echo "⚙️  Setting up environment..."
if [ -f ".env" ]; then
    scp .env admin@$VPS_IP:$DEPLOY_DIR/.env
    echo "✅ Environment file copied"
else
    echo "⚠️  Warning: .env file not found in current directory"
    echo "   Please copy it manually: scp .env admin@$VPS_IP:$DEPLOY_DIR/.env"
fi
echo ""

# Step 3: Start services via Docker Compose
echo "🐳 Building and starting Docker services..."
ssh admin@$VPS_IP << 'EOF'
    cd /opt/auto-trade-system
    
    # Build and start
    docker compose build
    docker compose up -d
    
    # Wait for health checks
    echo "Waiting for services to start..."
    sleep 30
    
    # Verify deployment
    echo ""
    echo "Service status:"
    docker compose ps
    echo ""
    
    # Check API health
    if curl -f http://localhost:8000/api/v1/health > /dev/null 2>&1; then
        echo "✅ API is healthy"
    else
        echo "⚠️  API not ready yet (may need more time)"
    fi
EOF

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Access your services:"
echo "  - Grafana Dashboard: http://$VPS_IP:3000"
echo "  - API Documentation: http://$VPS_IP:8000/docs"
echo "  - Prometheus: http://$VPS_IP:9090"
echo ""
echo "SSH access: ssh admin@$VPS_IP"
echo ""
echo "View logs: ssh admin@$VPS_IP 'cd /opt/auto-trade-system && docker compose logs -f'"
