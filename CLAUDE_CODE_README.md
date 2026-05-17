# Claude Code Setup for Auto-Trade-System

> **AI-Powered Development Environment** - Local setup guide for using Claude Code as your coding assistant

---

## 🚀 Get Started in 3 Steps

### Step 1: Install Dependencies (5 minutes)
```bash
# Update system and install Node.js 22.x + tmux
sudo apt update && sudo apt upgrade -y
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo bash -
sudo apt install -y nodejs tmux build-essential

# Install Claude Code
npm install -g @anthropic-ai/claude-code
```

### Step 2: Authenticate (2 minutes)
```bash
claude
# Follow the authentication link in your browser
```

### Step 3: Start Coding (1 minute)
```bash
tmux new -s claude-dev
cd /home/admin/.openclaw/workspace/auto-trade-system
source .venv/bin/activate
claude
```

**That's it!** You're now ready to use Claude Code for AI-assisted development.

---

## 📚 Documentation

Choose your path:

| Document | Purpose | When to Use |
|----------|---------|-------------|
| **[CLAUDE_CODE_QUICKREF.md](CLAUDE_CODE_QUICKREF.md)** | Quick reference & daily workflows | Daily use, troubleshooting |
| **[CLAUDE_CODE_LOCAL_SETUP_PLAN.md](CLAUDE_CODE_LOCAL_SETUP_PLAN.md)** | Comprehensive setup guide | First-time setup, detailed instructions |
| **[CLAUDE_CODE_SETUP_SUMMARY.md](CLAUDE_CODE_SETUP_SUMMARY.md)** | Implementation overview | Understanding what was delivered |

---

## ✅ Verify Your Setup

Run the automated verification script:
```bash
./scripts/verify_claude_setup.sh
```

This checks all 10 critical components and provides actionable feedback.

---

## 💡 What Can Claude Code Do?

Inside your Claude Code session, try these commands:

### Code Review & Analysis
```
Analyze app/core/execution_engine.py for race conditions
Review the risk engine architecture in app/risk_engine/
Find performance bottlenecks in the monitoring module
```

### Testing
```
Generate unit tests for app/paper_trading/session_manager.py
Run pytest on tests/integration/test_paper_trading.py
Check test coverage for app/exchange_connectors/
```

### Debugging
```
Why is my daily loss limit not triggering?
Debug the WebSocket reconnection mechanism
Find issues in the order retry logic
```

### Refactoring
```
Suggest improvements for app/signal_engine/
Optimize database queries in app/core/
Improve error handling patterns across the codebase
```

### Documentation
```
Generate API documentation for FastAPI endpoints
Create docstrings for app/exchange_connectors/bybit_client.py
Summarize recent changes from git log
```

---

## 🎯 Tmux Essentials

| Action | Command |
|--------|---------|
| New session | `tmux new -s name` |
| Attach session | `tmux attach -t name` |
| List sessions | `tmux ls` |
| Detach | `CTRL+B` then `D` |
| Split vertical | `CTRL+B` then `\|` |
| Split horizontal | `CTRL+B` then `-` |

See `CLAUDE_CODE_QUICKREF.md` for complete tmux cheat sheet.

---

## 🛠️ Tools Included

### Scripts
- **`scripts/verify_claude_setup.sh`** - Automated setup verification
- **`scripts/backup_workspace.sh`** - Automated backup with retention
- **`scripts/tmux.conf.example`** - Production-ready tmux configuration

### Configuration
Copy tmux config (optional but recommended):
```bash
cp scripts/tmux.conf.example ~/.tmux.conf
tmux source-file ~/.tmux.conf
```

### Backup
Manual backup:
```bash
./scripts/backup_workspace.sh
```

Automated daily backup (add to crontab):
```bash
crontab -e
# Add: 0 2 * * * /home/admin/.openclaw/workspace/auto-trade-system/scripts/backup_workspace.sh
```

---

## 🔧 Troubleshooting

### "command not found: claude"
```bash
export PATH=~/.npm-global/bin:$PATH
echo 'export PATH=~/.npm-global/bin:$PATH' >> ~/.bashrc
source ~/.bashrc
```

### Module import errors
```bash
# Activate virtual environment
source .venv/bin/activate

# Set PYTHONPATH
export PYTHONPATH=/home/admin/.openclaw/workspace/auto-trade-system:$PYTHONPATH
```

### Permission denied with npm
Use user-level npm installation:
```bash
mkdir ~/.npm-global
npm config set prefix '~/.npm-global'
echo 'export PATH=~/.npm-global/bin:$PATH' >> ~/.bashrc
source ~/.bashrc
npm install -g @anthropic-ai/claude-code
```

See `CLAUDE_CODE_QUICKREF.md` for complete troubleshooting guide.

---

## 📊 System Requirements

- **OS:** Linux (Ubuntu 24.04 LTS recommended)
- **RAM:** 4GB minimum, 8GB recommended
- **Disk:** 10GB free space
- **Python:** 3.11+ (already configured in `.venv`)
- **Node.js:** v22.x (installed by setup)
- **Internet:** Required for Claude Code authentication

---

## 🔐 Security Notes

This setup:
- ✓ Operates within your user permissions (`admin`)
- ✓ Does not modify root configurations
- ✓ Preserves existing security settings
- ✓ Uses your personal Anthropic account for authentication
- ✓ Keeps all data local to your machine

---

## 🎓 Learning Path

### Day 1: Basics
- Complete setup and authentication
- Learn basic tmux commands
- Ask simple code questions

### Week 1: Productivity
- Use Claude for debugging sessions
- Generate tests with AI assistance
- Refactor code with guidance

### Month 1: Mastery
- Multi-pane workflows (code + tests + logs)
- Custom prompts for trading system tasks
- Integrate with monitoring dashboards

---

## 🆘 Need Help?

1. **Run verification:** `./scripts/verify_claude_setup.sh`
2. **Check docs:** See documentation files listed above
3. **Troubleshoot:** Refer to `CLAUDE_CODE_QUICKREF.md`
4. **External docs:** https://docs.anthropic.com/claude-code

---

## 📈 What's Next?

After setup, consider:
- Setting up automated backups via cron
- Creating custom Claude prompts for your workflow
- Exploring advanced tmux features
- Integrating Claude insights with Prometheus metrics
- Building domain-specific AI skills for trading system development

---

**Ready to start?** Run:
```bash
./scripts/verify_claude_setup.sh
```

Then follow the quick start or full plan based on your preference.

Happy AI-assisted coding! 🚀
