# Claude Code - Quick Start Card

## ✅ Setup Status: COMPLETE

All components installed and verified. **Only authentication required.**

---

## 🔐 Step 1: Authenticate (One-Time)

```bash
claude
```

Follow the browser link to log in with your Anthropic account.

---

## 🚀 Step 2: Start Using

### Option A: With tmux (Recommended)
```bash
tmux new -s claude-dev
cd /home/admin/.openclaw/workspace/auto-trade-system
source .venv/bin/activate
claude
```

**Detach:** `CTRL+B` then `D`  
**Reattach:** `tmux attach -t claude-dev`

### Option B: Direct
```bash
cd /home/admin/.openclaw/workspace/auto-trade-system
source .venv/bin/activate
claude
```

---

## 💡 Try These Commands

Inside Claude Code session:

```
Analyze app/core/execution_engine.py for race conditions
Generate unit tests for app/risk_engine/
Debug the WebSocket reconnection mechanism
Suggest improvements for app/signal_engine/
Run pytest on tests/integration/test_paper_trading.py
```

---

## 🔧 Useful Commands

| Task | Command |
|------|---------|
| Verify setup | `./scripts/verify_claude_setup.sh` |
| Backup workspace | `./scripts/backup_workspace.sh` |
| Check tmux sessions | `tmux ls` |
| Update Claude Code | `npm update -g @anthropic-ai/claude-code` |

---

## 📚 Documentation

- **Getting Started:** [CLAUDE_CODE_README.md](CLAUDE_CODE_README.md)
- **Quick Reference:** [CLAUDE_CODE_QUICKREF.md](CLAUDE_CODE_QUICKREF.md)
- **Setup Complete:** [CLAUDE_CODE_SETUP_COMPLETE.md](CLAUDE_CODE_SETUP_COMPLETE.md)
- **Alibaba Linux Guide:** [CLAUDE_CODE_INSTALLATION_ALINUX.md](CLAUDE_CODE_INSTALLATION_ALINUX.md)

---

## ⚡ System Info

- **OS:** Alibaba Cloud Linux 3
- **Claude Code:** v2.1.143
- **Node.js:** v22.22.2
- **Python:** 3.11.15
- **tmux:** 2.7
- **Workspace:** `/home/admin/.openclaw/workspace/auto-trade-system`

---

**Ready to code!** Just run `claude` to authenticate and start. 🎉
