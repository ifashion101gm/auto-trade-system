# Claude Code Local Setup - Quick Reference Guide

**Purpose:** Quick setup guide for Claude Code on your local Linux environment  
**Workspace:** `/home/admin/.openclaw/workspace/auto-trade-system`  
**Last Updated:** May 17, 2026

---

## 🚀 Quick Start (5 Minutes)

### One-Liner Installation
```bash
# Install Node.js 22.x and Claude Code
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo bash - && \
sudo apt install -y nodejs tmux && \
npm install -g @anthropic-ai/claude-code && \
echo "Installation complete! Run 'claude' to authenticate."
```

### Start Using Claude Code
```bash
# 1. Authenticate (one-time)
claude

# 2. Start tmux session
tmux new -s claude-dev

# 3. Navigate and activate environment
cd /home/admin/.openclaw/workspace/auto-trade-system
source .venv/bin/activate

# 4. Run Claude Code
claude
```

---

## 📋 Prerequisites Check

Run the verification script:
```bash
./scripts/verify_claude_setup.sh
```

This checks:
- ✓ Node.js v22.x installed
- ✓ npm working
- ✓ Claude Code installed
- ✓ tmux available
- ✓ Python virtual environment exists
- ✓ Git configured
- ✓ Workspace structure intact

---

## 🔧 Manual Installation Steps

### Step 1: Install System Dependencies
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl git build-essential unzip tmux htop
```

### Step 2: Install Node.js 22.x
```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo bash -
sudo apt install -y nodejs
```

Verify:
```bash
node -v   # Should show v22.x.x
npm -v    # Should show version
```

### Step 3: Install Claude Code
```bash
npm install -g @anthropic-ai/claude-code
```

If you get permission errors, use user-level npm:
```bash
mkdir ~/.npm-global
npm config set prefix '~/.npm-global'
echo 'export PATH=~/.npm-global/bin:$PATH' >> ~/.bashrc
source ~/.bashrc
npm install -g @anthropic-ai/claude-code
```

### Step 4: Authenticate Claude Code
```bash
claude
```
- Follow the authentication link
- Log in with your Anthropic account
- Complete OAuth flow

### Step 5: Configure tmux (Optional but Recommended)
```bash
cp scripts/tmux.conf.example ~/.tmux.conf
tmux source-file ~/.tmux.conf
```

---

## 💻 Daily Workflow

### Starting a Claude Code Session
```bash
# Option 1: New tmux session
tmux new -s claude-dev
cd /home/admin/.openclaw/workspace/auto-trade-system
source .venv/bin/activate
claude

# Option 2: Attach to existing session
tmux attach -t claude-dev
```

### Common Claude Code Commands
Inside the Claude interactive session:

**Code Analysis:**
```
Analyze my execution engine for race conditions
Review the risk engine architecture
Find performance bottlenecks in app/core/
```

**Testing:**
```
Generate unit tests for app/paper_trading/session_manager.py
Run pytest on tests/integration/test_paper_trading.py
Check test coverage for app/risk_engine/
```

**Debugging:**
```
Why is my daily loss limit not triggering?
Find issues in the order retry logic
Debug the WebSocket reconnection mechanism
```

**Refactoring:**
```
Suggest improvements for app/signal_engine/
Optimize database queries in app/core/
Improve error handling patterns
```

**Documentation:**
```
Generate API documentation for FastAPI endpoints
Create docstrings for app/exchange_connectors/bybit_client.py
Summarize recent changes in git log
```

---

## 🎯 Tmux Quick Commands

| Action | Command |
|--------|---------|
| New session | `tmux new -s session-name` |
| List sessions | `tmux ls` |
| Attach to session | `tmux attach -t session-name` |
| Detach from session | `CTRL+B` then `D` |
| Kill session | `tmux kill-session -t session-name` |
| Split vertically | `CTRL+B` then `\|` |
| Split horizontally | `CTRL+B` then `-` |
| Switch panes | `CTRL+B` then arrow keys |
| Reload config | `CTRL+B` then `r` |
| Scroll mode | `CTRL+B` then `[` (use vi keys) |

---

## 🛠️ Troubleshooting

### Issue: "command not found: claude"
**Solution:**
```bash
# Check if npm global bin is in PATH
echo $PATH | grep npm

# If using user-level npm, ensure PATH is set
export PATH=~/.npm-global/bin:$PATH
echo 'export PATH=~/.npm-global/bin:$PATH' >> ~/.bashrc
```

### Issue: Claude Code can't import Python modules
**Solution:**
```bash
# Activate virtual environment before running claude
source .venv/bin/activate
claude

# Or set PYTHONPATH
export PYTHONPATH=/home/admin/.openclaw/workspace/auto-trade-system:$PYTHONPATH
```

### Issue: ModuleNotFoundError in Claude Code
**Solution:**
```bash
# Ensure PYTHONPATH is set in ~/.bashrc
echo 'export PYTHONPATH=/home/admin/.openclaw/workspace/auto-trade-system:$PYTHONPATH' >> ~/.bashrc
source ~/.bashrc
```

### Issue: tmux session lost after reboot
**Note:** This is expected behavior. Tmux sessions don't persist across reboots.
**Solution:** Simply recreate the session:
```bash
tmux new -s claude-dev
cd /home/admin/.openclaw/workspace/auto-trade-system
source .venv/bin/activate
claude
```

### Issue: npm permission denied
**Solution:** Use user-level npm installation (see Step 3 above)

### Issue: Claude Code authentication fails
**Solution:**
1. Check internet connection
2. Clear browser cache and retry
3. Try incognito/private browsing mode
4. Verify Anthropic account is active

---

## 📦 Backup & Restore

### Manual Backup
```bash
./scripts/backup_workspace.sh
```

### Automated Backup (Daily at 2 AM)
```bash
crontab -e
```
Add:
```
0 2 * * * /home/admin/.openclaw/workspace/auto-trade-system/scripts/backup_workspace.sh
```

### Restore from Backup
```bash
# List available backups
ls -lh ~/backups/auto-trade-system/

# Restore project files
tar xzf ~/backups/auto-trade-system/project_YYYYMMDD_HHMMSS.tar.gz -C /path/to/restore/

# Restore configs
tar xzf ~/backups/auto-trade-system/configs_YYYYMMDD_HHMMSS.tar.gz -C ~
```

---

## 🔍 Useful Commands

### Check System Resources
```bash
htop                    # Real-time resource monitoring
df -h                   # Disk space usage
free -m                 # Memory usage
du -sh .                # Current directory size
```

### Python Environment
```bash
source .venv/bin/activate   # Activate virtual environment
pip list                    # List installed packages
pip freeze > requirements.txt  # Export dependencies
```

### Git Operations
```bash
git status              # Check repository status
git log --oneline -10   # Last 10 commits
git diff                # Show unstaged changes
git branch -a           # List all branches
```

### Project-Specific
```bash
# Run tests
pytest tests/integration/test_paper_trading.py -v

# Check database
python3 scripts/check_db_connection.py

# View logs
tail -f logs/app.log
```

---

## 📚 Additional Resources

- **Full Setup Plan:** `CLAUDE_CODE_LOCAL_SETUP_PLAN.md`
- **tmux Configuration:** `scripts/tmux.conf.example`
- **Backup Script:** `scripts/backup_workspace.sh`
- **Verification Script:** `scripts/verify_claude_setup.sh`

---

## 🎓 Learning Curve

### Day 1: Basic Usage
- Install and authenticate Claude Code
- Learn basic tmux commands
- Ask simple code review questions

### Week 1: Productive Workflow
- Use Claude for debugging sessions
- Generate tests with AI assistance
- Refactor code with AI guidance

### Month 1: Advanced Integration
- Multi-pane workflows (code + tests + logs)
- Automated backup routines
- Custom Claude prompts for trading system tasks

---

## ⚡ Pro Tips

1. **Always activate venv before Claude:** Ensures access to all Python packages
2. **Use tmux for long sessions:** Prevents disconnection issues
3. **Set PYTHONPATH permanently:** Avoids import errors
4. **Backup before major changes:** Use the backup script
5. **Use specific file paths:** Helps Claude understand context
6. **Ask for explanations:** Claude can explain complex code sections
7. **Iterate on prompts:** Refine questions for better answers

---

## 🆘 Getting Help

If you encounter issues:

1. **Run verification script:** `./scripts/verify_claude_setup.sh`
2. **Check the full plan:** `CLAUDE_CODE_LOCAL_SETUP_PLAN.md`
3. **Review troubleshooting section** above
4. **Check Claude Code docs:** https://docs.anthropic.com/claude-code

---

**Happy coding with Claude Code! 🚀**
