# Claude Code Local Setup Plan

## Overview
Set up Claude Code on your current local Linux environment (`/home/admin/.openclaw/workspace/auto-trade-system`) as an AI coding assistant for trading system development. This plan focuses on installing Node.js, Claude Code, and tmux directly on your existing system while respecting the current project structure and permissions.

---

## Phase 1: System Preparation

### Step 1.1: Verify Current Environment
Check your current system state:
```bash
# Check OS version
cat /etc/os-release

# Check existing Python setup
python3 --version
which python3

# Check if virtual environment exists
ls -la /home/admin/.openclaw/workspace/auto-trade-system/.venv/

# Check current user and permissions
whoami
id
```

**Expected:** You're running as `admin` user with access to the workspace directory.

---

## Phase 2: Install Prerequisites

### Step 2.1: Update System Packages
```bash
sudo apt update && sudo apt upgrade -y
```

### Step 2.2: Install Essential Development Tools
```bash
sudo apt install -y \
    curl \
    git \
    build-essential \
    unzip \
    tmux \
    htop
```

**Verification:**
```bash
tmux -V
git --version
```

**Note:** Python3 and pip are already installed in your environment (per project memory).

---

## Phase 3: Node.js Installation

### Step 3.1: Install Node.js 22.x (Required for Claude Code)
```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo bash -
sudo apt install -y nodejs
```

### Step 3.2: Verify Installation
```bash
node -v   # Should show v22.x.x
npm -v    # Should show compatible npm version
```

**Important:** If you encounter permission issues with npm global installs, configure npm to use a user directory:
```bash
mkdir ~/.npm-global
npm config set prefix '~/.npm-global'
echo 'export PATH=~/.npm-global/bin:$PATH' >> ~/.bashrc
source ~/.bashrc
```

---

## Phase 4: Claude Code Installation

### Step 4.1: Install Claude Code Globally
```bash
npm install -g @anthropic-ai/claude-code
```

If using the npm user directory approach from Step 3.2:
```bash
npm install -g @anthropic-ai/claude-code
```

### Step 4.2: Verify Installation
```bash
claude --version
```

### Step 4.3: Authenticate Claude Code
```bash
claude
```
- This will provide an authentication link
- Open the link in your browser
- Log in with your Anthropic account
- Complete the OAuth flow
- Return to terminal - Claude Code is now authenticated

---

## Phase 5: Tmux Configuration for Persistent Sessions

### Step 5.1: Create Tmux Configuration
Create `~/.tmux.conf`:
```
# Set default shell
set-option -g default-shell /bin/bash

# Enable mouse support
set -g mouse on

# Set scrollback buffer
set -g history-limit 50000

# Better window splitting
bind | split-window -h
bind - split-window -v

# Status bar customization
set -g status-interval 5
set -g status-left '[#S] '
set -g status-right '%Y-%m-%d %H:%M'
```

Reload configuration:
```bash
tmux source-file ~/.tmux.conf
```

### Step 5.2: Tmux Workflow
**Start a new session:**
```bash
tmux new -s claude-dev
```

**Navigate to project and run Claude Code:**
```bash
cd /home/admin/.openclaw/workspace/auto-trade-system
source .venv/bin/activate  # Activate existing virtual environment
claude
```

**Detach safely:** Press `CTRL+B` then `D`

**Reattach later:**
```bash
tmux attach -t claude-dev
```

**List sessions:**
```bash
tmux ls
```

---

## Phase 6: Project Integration

### Step 6.1: Verify Existing Virtual Environment
Your project already has a `.venv` directory configured. Ensure it's working:
```bash
cd /home/admin/.openclaw/workspace/auto-trade-system
source .venv/bin/activate
python3 --version
pip list | head -20
```

**Per project memory:** The virtual environment should auto-activate based on your shell profile configuration.

### Step 6.2: Verify PYTHONPATH Configuration
Ensure the project can import local modules:
```bash
cd /home/admin/.openclaw/workspace/auto-trade-system
export PYTHONPATH=/home/admin/.openclaw/workspace/auto-trade-system:$PYTHONPATH
python3 -c "import app; print('Import successful')"
```

Add to `~/.bashrc` for persistence:
```bash
echo 'export PYTHONPATH=/home/admin/.openclaw/workspace/auto-trade-system:$PYTHONPATH' >> ~/.bashrc
source ~/.bashrc
```

### Step 6.3: Test Core Components
Verify your trading system components work:
```bash
cd /home/admin/.openclaw/workspace/auto-trade-system
source .venv/bin/activate

# Test database connectivity
python3 scripts/check_db_connection.py 2>/dev/null || echo "Script may not exist yet"

# Run existing test suite
pytest tests/integration/test_paper_trading.py -v --tb=short 2>/dev/null || echo "Tests may need setup"
```

---

## Phase 7: Claude Code Usage Workflow

### Step 7.1: Start Claude Code Session
```bash
tmux new -s claude-dev
cd /home/admin/.openclaw/workspace/auto-trade-system
source .venv/bin/activate
claude
```

### Step 7.2: Example Claude Code Commands
Inside the Claude Code interactive session, you can ask:

**Architecture Review:**
```
Analyze my execution engine in app/core/execution_engine.py for race conditions
```

**Code Optimization:**
```
Optimize Prometheus metrics usage in the monitoring module at app/monitoring/
```

**Debugging:**
```
Find weaknesses in my order retry system in app/exchange_connectors/
```

**Testing:**
```
Generate unit tests for the risk engine module at app/risk_engine/
```

**Refactoring:**
```
Review the signal engine architecture in app/signal_engine/ and suggest improvements
```

### Step 7.3: File Operations
Claude Code can:
- Read files: `read app/core/execution_engine.py`
- Edit files: `edit app/core/execution_engine.py`
- Run commands: `run pytest tests/test_execution.py`
- Analyze codebase structure
- Suggest architectural changes

**Important:** Claude Code will respect your existing file permissions and won't modify files outside the workspace without explicit commands.

---

## Phase 8: Git Integration

### Step 8.1: Configure Git (if not already configured)
```bash
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

### Step 8.2: Verify Repository Status
```bash
cd /home/admin/.openclaw/workspace/auto-trade-system
git status
git branch
```

### Step 8.3: Claude-Assisted Git Operations
Inside Claude Code, you can ask:
```
Review my recent changes and suggest a commit message
```
```
Generate a PR summary for the changes in app/paper_trading/
```

---

## Phase 9: Backup & Maintenance

### Step 9.1: Create Local Backup Script
Create `~/scripts/backup_workspace.sh`:
```bash
#!/bin/bash
BACKUP_DIR=~/backups/auto-trade-system
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
WORKSPACE=/home/admin/.openclaw/workspace/auto-trade-system

mkdir -p $BACKUP_DIR

# Backup project files (excluding .venv and large directories)
tar czf $BACKUP_DIR/project_$TIMESTAMP.tar.gz \
    --exclude='.venv' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='logs/*' \
    --exclude='.pytest_cache' \
    -C $WORKSPACE .

# Backup configs
tar czf $BACKUP_DIR/configs_$TIMESTAMP.tar.gz ~/.tmux.conf ~/.bashrc

# Keep last 7 backups
ls -t $BACKUP_DIR/*.tar.gz | tail -n +8 | xargs rm -f 2>/dev/null || true

echo "Backup completed: $BACKUP_DIR/project_$TIMESTAMP.tar.gz"
```

Make executable:
```bash
mkdir -p ~/scripts
chmod +x ~/scripts/backup_workspace.sh
```

### Step 9.2: Optional - Automated Backups
Add to crontab (daily at 2 AM):
```bash
crontab -e
```
```
0 2 * * * /home/admin/scripts/backup_workspace.sh
```

### Step 9.3: System Monitoring
Monitor your local system resources:
```bash
htop        # Real-time resource usage
df -h       # Disk space
free -m     # Memory usage
du -sh /home/admin/.openclaw/workspace/auto-trade-system  # Project size
```

---

## Verification Checklist

After completing all phases, verify:

- [ ] Node.js 22.x is installed and accessible (`node -v`)
- [ ] npm is working correctly (`npm -v`)
- [ ] Claude Code is installed (`claude --version`)
- [ ] Claude Code is authenticated (can run `claude` successfully)
- [ ] Tmux sessions persist after disconnection
- [ ] Existing Python virtual environment works (`.venv/bin/activate`)
- [ ] PYTHONPATH is configured for local imports
- [ ] Claude Code can read/edit files in `/home/admin/.openclaw/workspace/auto-trade-system`
- [ ] Git repository is accessible and configured
- [ ] Can start Claude Code inside tmux session within the project directory
- [ ] Claude Code can run pytest commands successfully
- [ ] Backup script runs without errors

---

## Integration with Existing Trading System

### Compatible Components
Your existing auto-trade-system architecture includes:
- ✅ FastAPI application (`app/`)
- ✅ Risk engine (`app/risk_engine/`)
- ✅ Execution layer (`app/core/execution_engine.py`)
- ✅ Paper trading system (`app/paper_trading/`)
- ✅ Shadow mode (`app/shadow_mode/`)
- ✅ Prometheus monitoring (`app/monitoring/`)
- ✅ Exchange connectors (Bybit, Binance)
- ✅ PostgreSQL/SQLite databases
- ✅ Redis caching

### Claude Code Use Cases for Your System
1. **Code Review:** Analyze execution engine for race conditions
2. **Test Generation:** Create unit tests for risk engine modules
3. **Performance Optimization:** Optimize Prometheus metrics usage
4. **Debugging:** Find weaknesses in order retry systems
5. **Documentation:** Generate API documentation from code
6. **Refactoring:** Improve module organization and imports
7. **Configuration Review:** Validate environment variable usage

---

## Estimated Time
- **Prerequisites Installation (Phases 1-3):** 15-20 minutes
- **Claude Code Setup (Phase 4):** 10-15 minutes (includes authentication)
- **Tmux Configuration (Phase 5):** 5-10 minutes
- **Project Integration (Phases 6-8):** 15-20 minutes
- **Total:** ~45-65 minutes

---

## Important Notes

### Permissions
- All installations respect your current user (`admin`) permissions
- No root-level changes except package installation via `sudo`
- Claude Code operates within your workspace directory permissions

### Existing Configuration Preserved
- Your `.venv` virtual environment remains unchanged
- Existing `.env` file and environment variables are preserved
- Database configurations (PostgreSQL/SQLite) remain intact
- All existing scripts and monitoring setups continue to work

### Security
- No SSH key configuration needed (local environment)
- No firewall changes required (local only)
- Claude Code authentication uses your personal Anthropic account
- All operations stay within your user home directory

---

## Troubleshooting

### Issue: npm global install permission denied
**Solution:** Use the npm user directory approach from Phase 3, Step 3.2

### Issue: Claude Code can't find Python packages
**Solution:** Always activate the virtual environment before starting Claude Code:
```bash
source .venv/bin/activate
claude
```

### Issue: Module import errors in Claude Code
**Solution:** Ensure PYTHONPATH is set:
```bash
export PYTHONPATH=/home/admin/.openclaw/workspace/auto-trade-system:$PYTHONPATH
```

### Issue: Tmux session lost after reboot
**Solution:** Tmux sessions don't persist across reboots. Simply recreate:
```bash
tmux new -s claude-dev
cd /home/admin/.openclaw/workspace/auto-trade-system
source .venv/bin/activate
claude
```

---

## Next Steps (Future Enhancements)

Once the local setup is complete, consider:

1. **Docker Integration:** Use Docker for isolated testing environments
2. **CI/CD Pipeline:** Set up GitHub Actions for automated testing
3. **Advanced Monitoring:** Integrate Claude Code insights with Prometheus metrics
4. **Multi-Session Workflow:** Use multiple tmux windows for different tasks
5. **Custom Claude Skills:** Create domain-specific skills for trading system development

---

This plan provides a streamlined setup for using Claude Code as your local AI coding assistant while maintaining full compatibility with your existing auto-trade-system architecture and development workflow.
