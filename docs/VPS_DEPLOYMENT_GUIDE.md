# VPS Deployment Guide

## Overview

This guide walks through deploying the Auto Trade System to a Singapore VPS with Tailscale for secure remote access. This setup provides production-ready infrastructure with encrypted mesh networking.

## Architecture

```
Your Laptop
    ↓ (Tailscale Mesh Network - Encrypted)
Singapore VPS (Ubuntu 22.04)
    ├── Tailscale Client (Exit Node)
    ├── Docker Compose Stack
    │   ├── PostgreSQL (Database)
    │   ├── Redis (Cache & Events)
    │   ├── Trading Bot (FastAPI - Port 8000)
    │   ├── Trading Worker (Background Tasks)
    │   ├── Prometheus (Metrics - Port 9090)
    │   └── Grafana (Dashboards - Port 3000)
    └── Claude Code CLI (Optional - for AI coding)
```

### Why This Architecture?

- **Tailscale**: Encrypted peer-to-peer network, no public ports exposed
- **Docker Compose**: Isolated, reproducible deployments
- **Singapore VPS**: Low-latency access to Asian crypto exchanges
- **Remote SSH Development**: Edit locally, execute remotely

## Prerequisites

### VPS Requirements

- **OS**: Ubuntu 22.04 LTS
- **CPU**: Minimum 2 cores
- **RAM**: Minimum 2GB (4GB recommended)
- **Storage**: 50GB SSD minimum
- **Region**: Singapore (for optimal exchange API latency)

### Recommended Providers

| Provider | Plan | Monthly Cost | Specs |
|----------|------|--------------|-------|
| DigitalOcean | Basic Droplet | $12 | 2GB RAM, 1 CPU, 50GB SSD |
| Vultr | Cloud Compute | $12 | 2GB RAM, 1 CPU, 55GB SSD |
| Linode/Akamai | Shared CPU | $12 | 2GB RAM, 1 CPU, 50GB SSD |
| AWS EC2 | t3.small | ~$15 | 2GB RAM, 2 CPU, EBS storage |
| Hetzner | CPX21 | ~€5 | 2GB RAM, 2 CPU, 40GB SSD |

**Recommendation**: DigitalOcean or Vultr for ease of use and Singapore regions.

### Laptop Requirements

- Tailscale installed: https://tailscale.com/download
- VS Code with Remote SSH extension (optional, for remote development)
- SSH client (built-in on macOS/Linux, Git Bash on Windows)

## Step-by-Step Setup

### Step 1: Provision VPS

1. Sign up for your chosen VPS provider
2. Create a new droplet/instance:
   - Select **Ubuntu 22.04 LTS**
   - Choose **Singapore** region
   - Select **2GB RAM / 2 CPU** minimum
   - Add your SSH key (recommended) or use password
3. Note down the public IP address
4. Wait for instance to be ready (usually 1-2 minutes)

### Step 2: Initial SSH Connection

Connect to your VPS using the public IP:

```bash
ssh root@<vps-public-ip>
```

Create a non-root user (if not done during provisioning):

```bash
adduser admin
usermod -aG sudo admin
usermod -aG docker admin  # If Docker pre-installed
su - admin
```

### Step 3: Clone Repository

```bash
cd ~
git clone https://github.com/your-repo/auto-trade-system.git
cd auto-trade-system
```

### Step 4: Run Setup Scripts

All scripts are in the `scripts/vps/` directory. Run them in order:

#### 4.1 Setup VPS Base System

```bash
./scripts/vps/setup_vps.sh
```

This will:
- Update system packages
- Install Docker, Node.js, Git, and utilities
- Configure firewall (UFW)
- Set up basic security

**Duration**: 5-10 minutes

#### 4.2 Install Tailscale

```bash
./scripts/vps/install_tailscale.sh
```

This will:
- Install Tailscale client
- Start authentication process
- Display a login URL

**Action Required**:
1. Copy the URL displayed
2. Open it in your browser
3. Login with Google/GitHub/Microsoft account
4. Authorize the device

**Important**: Use the **same account** you'll use on your laptop!

#### 4.3 Enable Exit Node

After authenticating in the browser:

```bash
./scripts/vps/enable_tailscale_exit_node.sh
```

This will:
- Configure VPS as Tailscale exit node
- Display your Tailscale IP (starts with `100.x.x.x`)
- Show connection status

**Note the Tailscale IP** - you'll need it for the next steps.

#### 4.4 Approve Exit Node (Admin Console)

1. Go to [Tailscale Admin Console](https://login.tailscale.com/admin/machines)
2. Find your VPS in the machine list
3. Click "..." → "Enable exit node"
4. Confirm the action

#### 4.5 Validate Environment

```bash
./scripts/vps/validate_vps_env.sh
```

This checks:
- Docker and Docker Compose installation
- Tailscale connectivity
- System resources (disk, memory)
- Firewall status

**Expected output**: All checks should pass ✅

### Step 5: Configure Laptop

#### 5.1 Install Tailscale on Laptop

Download from: https://tailscale.com/download

Install and login with the **same account** used for VPS.

#### 5.2 Enable Exit Node Routing

**Windows/macOS**:
1. Open Tailscale app
2. Click menu → Settings
3. Find "Exit Nodes" section
4. Select your Singapore VPS
5. Toggle "Use exit node" ON

**Linux**:
```bash
tailscale up --exit-node=<tailscale-ip> --exit-node-allow-lan-access=true
```

#### 5.3 Verify Routing

Visit https://whatismyipaddress.com

You should see a **Singapore IP address**, confirming traffic routes through VPS.

### Step 6: Deploy Application

#### 6.1 Configure Environment

On your **laptop**, create/edit `.env` file:

```bash
cp .env.example .env
nano .env
```

Fill in required values:
- `DATABASE_URL` (use provided default for Docker)
- `BYBIT_API_KEY` and `BYBIT_API_SECRET`
- `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`
- LLM API keys (OpenAI, Anthropic, etc.)
- Strong passwords for `DB_PASSWORD` and `GRAFANA_PASSWORD`

**Never commit `.env` to git!**

#### 6.2 Deploy to VPS

From your laptop (in project directory):

```bash
./scripts/vps/deploy_to_vps.sh <tailscale-ip>
```

Or if Tailscale is configured:

```bash
./scripts/vps/deploy_to_vps.sh
```

This will:
- Clone/pull repository on VPS
- Copy `.env` file securely via SCP
- Build Docker images
- Start all services
- Verify health checks

**Duration**: 5-10 minutes (first build takes longer)

### Step 7: Access Services

All services are accessible via Tailscale IP:

- **Grafana Dashboard**: http://<tailscale-ip>:3000
  - Default login: `admin` / password from `.env`
  - Pre-configured dashboards for trading metrics
  
- **API Documentation**: http://<tailscale-ip>:8000/docs
  - Interactive Swagger UI
  - Test API endpoints directly
  
- **Prometheus**: http://<tailscale-ip>:9090
  - Raw metrics queries
  - Service discovery
  
- **SSH Access**: `ssh admin@<tailscale-ip>`

## Security Considerations

### Network Security

- ✅ **Tailscale encryption**: All traffic encrypted WireGuard tunnels
- ✅ **No public ports**: Services only accessible via Tailscale
- ✅ **Firewall enabled**: UFW blocks unauthorized access
- ✅ **SSH hardened**: Key-based auth, root login disabled

### Application Security

- 🔐 **Environment variables**: Secrets stored in `.env`, never in code
- 🔐 **Database passwords**: Strong passwords required by Docker Compose
- 🔐 **API keys**: Exchange credentials encrypted at rest
- 🔐 **Non-root containers**: Docker runs as unprivileged user

### Best Practices

1. **Rotate API keys** regularly
2. **Update dependencies** monthly: `docker compose pull && docker compose up -d`
3. **Monitor logs**: `docker compose logs -f`
4. **Backup database**: See maintenance section below
5. **Review Tailscale ACLs**: Limit access if team grows

## Maintenance

### Updating Application

To deploy latest code changes:

```bash
./scripts/vps/deploy_to_vps.sh
```

This pulls latest from git and restarts services.

### Viewing Logs

```bash
# SSH into VPS
ssh admin@<tailscale-ip>

# View all logs
cd /opt/auto-trade-system
docker compose logs -f

# View specific service
docker compose logs -f trading-bot
docker compose logs -f trading-worker

# View last 100 lines
docker compose logs --tail=100 trading-bot
```

### Backup Database

#### Manual Backup

```bash
ssh admin@<tailscale-ip>
cd /opt/auto-trade-system

# Create backup
docker compose exec postgres pg_dump -U trading vmassit > backup_$(date +%Y%m%d_%H%M%S).sql

# Copy to laptop
scp admin@<tailscale-ip>:/opt/auto-trade-system/backup_*.sql ./backups/
```

#### Automated Backups

The system includes automated backup scripts:

```bash
# On VPS
cd /opt/auto-trade-system

# Run backup script
./scripts/backup_database.sh

# Enable systemd timer for daily backups
sudo systemctl enable --now vmassit-backup.timer
```

### Restore Database

```bash
# Copy backup to VPS
scp backup_YYYYMMDD_HHMMSS.sql admin@<tailscale-ip>:/opt/auto-trade-system/

# SSH into VPS
ssh admin@<tailscale-ip>
cd /opt/auto-trade-system

# Restore
./scripts/restore_database.sh backup_YYYYMMDD_HHMMSS.sql
```

### Monitoring Resources

```bash
# Check container resource usage
docker stats

# Check disk usage
df -h

# Check memory
free -m

# Check CPU load
htop
```

### Restarting Services

```bash
# Restart all services
docker compose restart

# Restart specific service
docker compose restart trading-bot

# Full rebuild (if dependencies changed)
docker compose down
docker compose build
docker compose up -d
```

## Troubleshooting

### Tailscale Not Connecting

```bash
# Check status
sudo tailscale status

# Reconnect
sudo tailscale up --advertise-exit-node

# Check if exit node approved
# Visit: https://login.tailscale.com/admin/machines
```

### Docker Services Down

```bash
# Check service status
docker compose ps

# View logs for errors
docker compose logs --tail=100

# Restart failed service
docker compose restart <service-name>

# Rebuild if needed
docker compose up -d --build
```

### High API Latency

Check VPS resources:

```bash
htop          # CPU/Memory usage
df -h         # Disk space
docker stats  # Container resources
```

If resources are low:
- Upgrade VPS plan
- Optimize Docker resource limits in `docker-compose.yml`
- Clean up unused containers: `docker system prune`

### Database Connection Issues

```bash
# Check PostgreSQL is running
docker compose ps postgres

# View PostgreSQL logs
docker compose logs postgres

# Test connection
docker compose exec postgres psql -U trading -d vmassit -c "SELECT 1;"
```

### Cannot Access Grafana/API

1. Verify Tailscale is connected on laptop
2. Check exit node is selected in Tailscale settings
3. Verify services are running: `docker compose ps`
4. Check firewall on VPS: `sudo ufw status`
5. Try accessing via SSH tunnel:
   ```bash
   ssh -L 3000:localhost:3000 admin@<tailscale-ip>
   # Then visit http://localhost:3000
   ```

### Deployment Script Fails

Common issues:

1. **SSH permission denied**: Ensure SSH key is added to VPS
   ```bash
   ssh-copy-id admin@<tailscale-ip>
   ```

2. **Docker permission denied**: Add user to docker group
   ```bash
   sudo usermod -aG docker admin
   # Logout and login again
   ```

3. **Port already in use**: Check for conflicting services
   ```bash
   sudo lsof -i :8000
   sudo lsof -i :3000
   ```

## Advanced Configuration

### Custom Docker Resource Limits

Edit `docker-compose.yml` to adjust resource limits:

```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'
      memory: 2G
    reservations:
      cpus: '0.5'
      memory: 512M
```

### Adding Custom Domains

If you want custom domains instead of IPs:

1. Point DNS to Tailscale Funnel (requires Tailscale premium)
2. Or set up reverse proxy (nginx/caddy) on VPS

### Multi-User Access

For team access:

1. Invite users to your Tailscale network
2. Configure Tailscale ACLs to restrict access
3. Share SSH keys securely
4. Consider using Tailscale SSH for additional security

## Performance Optimization

### Database Tuning

PostgreSQL is already configured with optimized settings in `docker-compose.yml`:

- `shared_buffers`: 256MB
- `effective_cache_size`: 768MB
- `work_mem`: 4MB
- `max_connections`: 100

Adjust based on your VPS specs.

### Redis Caching

Redis is configured with append-only mode for persistence. Monitor memory usage:

```bash
docker compose exec redis redis-cli info memory
```

### Docker Cleanup

Regular cleanup prevents disk space issues:

```bash
# Remove unused images
docker image prune -a

# Remove stopped containers
docker container prune

# Remove unused volumes
docker volume prune

# One-command cleanup
docker system prune -a --volumes
```

## Support & Resources

### Documentation

- [Remote Development Guide](VPS_REMOTE_DEVELOPMENT.md) - VS Code Remote SSH setup
- [README](../README.md) - Project overview
- [Docker Compose Reference](https://docs.docker.com/compose/)

### Logs Locations

- Application logs: `/opt/auto-trade-system/logs/`
- Docker logs: `docker compose logs <service>`
- System logs: `sudo journalctl -u docker`

### Emergency Contacts

If critical issues arise:

1. Check logs first: `docker compose logs --tail=100`
2. Review health endpoint: `curl http://<tailscale-ip>:8000/api/v1/health`
3. Restart services: `docker compose restart`
4. Rollback to previous version: `git checkout <commit> && docker compose up -d`

---

**Deployment complete! Your trading system is now running securely on Singapore VPS. 🚀**
