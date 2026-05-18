# Remote Development with VPS

## Overview

This guide explains how to use VS Code Remote SSH to develop on your Singapore VPS while editing code locally. This provides the best of both worlds: local editing convenience with remote execution power.

## Prerequisites

- VS Code installed on laptop
- Remote - SSH extension installed in VS Code
- Tailscale connected to VPS
- SSH key-based authentication configured

## Architecture

```
Laptop (VS Code)
    ↓ (SSH over Tailscale encrypted tunnel)
Singapore VPS
    ↓ (Docker Compose)
Trading System + Claude APIs
```

### Benefits

- **Code edits happen locally** - Fast, responsive editing
- **Execution happens on VPS** - Singapore IP for trading APIs
- **Claude Code runs remotely** - Stable connectivity, no token interruptions
- **No local dependencies** - Everything runs on VPS
- **Production-like environment** - Test in actual deployment environment

## Setup Steps

### Step 1: Configure SSH Access

Add the following to your `~/.ssh/config` file on your laptop:

```ssh-config
Host vps-trading
    HostName <tailscale-ip>
    User admin
    IdentityFile ~/.ssh/id_ed25519
    ForwardAgent yes
    ServerAliveInterval 60
    ServerAliveCountMax 3
```

Replace `<tailscale-ip>` with your VPS Tailscale IP (get it with `tailscale ip -4` on VPS).

### Step 2: Set Up SSH Key Authentication

If you haven't already set up SSH keys:

```bash
# On your laptop
ssh-keygen -t ed25519 -C "your_email@example.com"

# Copy public key to VPS
ssh-copy-id admin@<tailscale-ip>

# Test connection
ssh admin@<tailscale-ip>
```

### Step 3: Connect via VS Code

1. Open VS Code on your laptop
2. Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on Mac)
3. Type "Remote-SSH: Connect to Host"
4. Select `vps-trading` from the list
5. A new VS Code window will open connected to the VPS
6. Click "Open Folder" and navigate to `/opt/auto-trade-system`

### Step 4: Install Extensions on Remote

When you first connect, VS Code will prompt you to install extensions on the remote host. Recommended extensions:

- Python
- Docker
- GitLens
- Pylance
- REST Client (for API testing)

## Using Claude Code on VPS

### Option 1: Claude Code CLI

```bash
# SSH into VPS
ssh admin@<tailscale-ip>

# Navigate to project
cd /opt/auto-trade-system

# Install Claude Code (if not already installed)
npm install -g @anthropic-ai/claude-code

# Run Claude
claude
```

### Option 2: VS Code Integration

1. Install "Claude Code" extension in VS Code
2. When connected via Remote SSH, Claude will run on the VPS
3. All API calls will originate from Singapore IP

### Option 3: Terminal in VS Code

1. Open terminal in VS Code (`Ctrl+``)
2. It will automatically be a remote terminal on the VPS
3. Run any commands as if you were SSH'd in

## Development Workflow

### Editing Code

1. Make changes in VS Code (files are edited on VPS)
2. Save files (`Ctrl+S`)
3. Changes are immediately on the VPS filesystem

### Running Tests

```bash
# In VS Code terminal (remote)
python -m pytest tests/ -v

# Or run specific test
python scripts/vps/test_hybrid_deployment.py
```

### Deploying Changes

```bash
# Restart Docker services to pick up code changes
docker compose restart trading-bot trading-worker

# Or rebuild if dependencies changed
docker compose build && docker compose up -d
```

### Viewing Logs

```bash
# View live logs in VS Code terminal
docker compose logs -f trading-bot

# Or view specific service
docker compose logs -f trading-worker
```

## Tips & Best Practices

### Performance Optimization

- **Use VS Code settings sync** to keep settings consistent
- **Enable auto-save** to prevent lost changes
- **Use tmux** for long-running processes:
  ```bash
  tmux new -s trading
  # Run your process
  # Detach with Ctrl+B, D
  # Reattach with: tmux attach -s trading
  ```

### File Synchronization

Since you're editing directly on the VPS, there's no need for file sync tools. However, for backup:

```bash
# Pull latest from git
git pull origin main

# Push your changes
git add .
git commit -m "Your message"
git push origin main
```

### Database Access

```bash
# Connect to PostgreSQL on VPS
docker compose exec postgres psql -U trading -d vmassit

# Or from your laptop via SSH tunnel
ssh -L 5432:localhost:5432 admin@<tailscale-ip>
# Then connect to localhost:5432 from laptop
```

### Port Forwarding

Access VPS services from your laptop:

```bash
# Forward Grafana
ssh -L 3000:localhost:3000 admin@<tailscale-ip>
# Access: http://localhost:3000

# Forward API docs
ssh -L 8000:localhost:8000 admin@<tailscale-ip>
# Access: http://localhost:8000/docs
```

## Troubleshooting

### Connection Drops

If SSH connection drops frequently:

1. Add to `~/.ssh/config`:
   ```ssh-config
   ServerAliveInterval 60
   ServerAliveCountMax 3
   ```

2. Use tmux to keep sessions alive:
   ```bash
   tmux new -s dev
   # Work in tmux session
   # Even if SSH drops, session persists
   ```

### Slow Performance

- Check VPS resources: `htop`, `df -h`, `free -m`
- Close unused Docker containers: `docker system prune`
- Limit VS Code extensions on remote

### Permission Issues

If you get permission denied errors:

```bash
# Fix ownership
sudo chown -R admin:admin /opt/auto-trade-system

# Or add yourself to docker group
sudo usermod -aG docker admin
# Then logout and login again
```

### Tailscale Connectivity

If Tailscale stops working:

```bash
# Check status
tailscale status

# Reconnect
sudo tailscale up --advertise-exit-node

# Check firewall
sudo ufw status
```

## Security Considerations

- **Always use SSH keys**, never password authentication
- **Keep Tailscale updated** on both laptop and VPS
- **Use strong passwords** for Grafana and database
- **Regular backups** of `.env` file and database
- **Monitor access logs**: `sudo tail -f /var/log/auth.log`

## Next Steps

Once comfortable with remote development:

1. Set up automated deployments with CI/CD
2. Configure monitoring alerts via Telegram
3. Implement automated backup strategies
4. Explore advanced VS Code remote features (port forwarding, tunnels)

---

**Happy coding! 🚀**
