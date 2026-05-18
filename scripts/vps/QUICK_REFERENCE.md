# VPS Deployment Quick Reference

**Quick commands for VPS deployment with Tailscale**

## Prerequisites Checklist

- [ ] Singapore VPS provisioned (Ubuntu 22.04, 2GB+ RAM)
- [ ] SSH access to VPS configured
- [ ] Tailscale account created
- [ ] `.env` file configured with required variables

## VPS Setup (Run on VPS)

```bash
# 1. Clone repository
git clone https://github.com/your-repo/auto-trade-system.git
cd auto-trade-system

# 2. Run setup script
./scripts/vps/setup_vps.sh

# 3. Install Tailscale
./scripts/vps/install_tailscale.sh
# → Follow the authentication URL in browser

# 4. Enable exit node
./scripts/vps/enable_tailscale_exit_node.sh
# → Note the Tailscale IP (100.x.x.x)

# 5. Validate environment
./scripts/vps/validate_vps_env.sh
```

## Laptop Setup

```bash
# 1. Install Tailscale from https://tailscale.com/download

# 2. Login with same account as VPS

# 3. Enable exit node
# Windows/macOS: Tailscale app → Settings → Exit Nodes → Select VPS
# Linux: tailscale up --exit-node=<vps-ip>

# 4. Verify routing
curl https://api.ipify.org  # Should show Singapore IP
```

## Deploy Application (From Laptop)

```bash
# Navigate to project directory
cd /path/to/auto-trade-system

# Deploy to VPS
./scripts/vps/deploy_to_vps.sh <tailscale-ip>

# Or if Tailscale configured:
./scripts/vps/deploy_to_vps.sh
```

## Access Services

Replace `<tailscale-ip>` with your VPS Tailscale IP:

- **Grafana**: http://<tailscale-ip>:3000
- **API Docs**: http://<tailscale-ip>:8000/docs
- **Prometheus**: http://<tailscale-ip>:9090
- **SSH**: `ssh admin@<tailscale-ip>`

## Common Commands

### View Logs
```bash
ssh admin@<tailscale-ip>
cd /opt/auto-trade-system
docker compose logs -f trading-bot
```

### Restart Services
```bash
ssh admin@<tailscale-ip>
cd /opt/auto-trade-system
docker compose restart
```

### Update Application
```bash
# From laptop
./scripts/vps/deploy_to_vps.sh
```

### Backup Database
```bash
ssh admin@<tailscale-ip>
cd /opt/auto-trade-system
./scripts/backup_database.sh
```

## Validation

```bash
# Test hybrid deployment configuration
python3 scripts/vps/test_hybrid_deployment.py

# Run integration tests
bash scripts/vps/run_integration_test.sh
```

## Troubleshooting

### Tailscale Not Connecting
```bash
sudo tailscale status
sudo tailscale up --advertise-exit-node
```

### Docker Services Down
```bash
docker compose ps
docker compose logs --tail=100
docker compose restart
```

### Can't Access Services
1. Verify Tailscale connected on laptop
2. Check exit node selected
3. Verify services running: `docker compose ps`
4. Try SSH tunnel: `ssh -L 3000:localhost:3000 admin@<tailscale-ip>`

## File Locations

- **Scripts**: `scripts/vps/`
- **Documentation**: `docs/VPS_*.md`
- **Docker Config**: `docker-compose.yml`
- **Environment**: `.env` (create from `.env.example`)

## Required .env Variables

```bash
DB_PASSWORD=strong_password_here
GRAFANA_PASSWORD=strong_password_here
BYBIT_API_KEY=your_api_key
BYBIT_API_SECRET=your_api_secret
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

## Resources

- Full Guide: `docs/VPS_DEPLOYMENT_GUIDE.md`
- Remote Dev: `docs/VPS_REMOTE_DEVELOPMENT.md`
- Implementation: `VPS_DEPLOYMENT_IMPLEMENTATION_SUMMARY.md`

---

**For detailed instructions, see docs/VPS_DEPLOYMENT_GUIDE.md**
