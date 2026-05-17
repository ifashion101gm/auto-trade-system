# Claude Code Setup Checklist

**Workspace:** `/home/admin/.openclaw/workspace/auto-trade-system`  
**Date Started:** _______________  
**Date Completed:** _______________

---

## Phase 1: System Preparation ☐

- [ ] System packages updated (`sudo apt update && sudo apt upgrade -y`)
- [ ] Essential tools installed (curl, git, build-essential, unzip, tmux, htop)
- [ ] Verified installations:
  - [ ] `tmux -V` works
  - [ ] `git --version` works
  - [ ] `python3 --version` shows Python 3.11+

**Status:** ☐ Complete ☐ In Progress ☐ Not Started

---

## Phase 2: Node.js Installation ☐

- [ ] NodeSource repository added (Node.js 22.x)
- [ ] Node.js installed (`sudo apt install -y nodejs`)
- [ ] Verified installation:
  - [ ] `node -v` shows v22.x.x
  - [ ] `npm -v` shows version number

**Troubleshooting:**
- If permission issues with npm global installs, set up user-level npm:
  ```bash
  mkdir ~/.npm-global
  npm config set prefix '~/.npm-global'
  echo 'export PATH=~/.npm-global/bin:$PATH' >> ~/.bashrc
  source ~/.bashrc
  ```

**Status:** ☐ Complete ☐ In Progress ☐ Not Started

---

## Phase 3: Claude Code Installation ☐

- [ ] Claude Code installed globally (`npm install -g @anthropic-ai/claude-code`)
- [ ] Verified installation (`claude --version`)
- [ ] Authenticated with Anthropic account:
  - [ ] Ran `claude` command
  - [ ] Opened authentication link in browser
  - [ ] Logged in with Anthropic account
  - [ ] Completed OAuth flow
  - [ ] Confirmed authentication successful

**Status:** ☐ Complete ☐ In Progress ☐ Not Started

---

## Phase 4: Tmux Configuration ☐

- [ ] Copied tmux configuration:
  ```bash
  cp scripts/tmux.conf.example ~/.tmux.conf
  ```
- [ ] Loaded configuration (`tmux source-file ~/.tmux.conf`)
- [ ] Tested basic tmux operations:
  - [ ] Created new session (`tmux new -s test`)
  - [ ] Detached from session (CTRL+B then D)
  - [ ] Reattached to session (`tmux attach -t test`)
  - [ ] Killed test session (`tmux kill-session -t test`)

**Status:** ☐ Complete ☐ In Progress ☐ Not Started

---

## Phase 5: Project Integration ☐

- [ ] Virtual environment verified:
  - [ ] `.venv` directory exists
  - [ ] Can activate: `source .venv/bin/activate`
  - [ ] Python packages accessible after activation

- [ ] PYTHONPATH configured:
  - [ ] Added to `~/.bashrc`:
    ```bash
    export PYTHONPATH=/home/admin/.openclaw/workspace/auto-trade-system:$PYTHONPATH
    ```
  - [ ] Reloaded bashrc: `source ~/.bashrc`
  - [ ] Tested import: `python3 -c "import app; print('Success')"`

- [ ] Git configuration:
  - [ ] User name set: `git config user.name`
  - [ ] User email set: `git config user.email`
  - [ ] Repository status checked: `git status`

**Status:** ☐ Complete ☐ In Progress ☐ Not Started

---

## Phase 6: Verification ☐

- [ ] Ran verification script: `./scripts/verify_claude_setup.sh`
- [ ] All checks passed (or warnings addressed):
  - [ ] Node.js v22.x ✓
  - [ ] npm working ✓
  - [ ] Claude Code installed ✓
  - [ ] tmux available ✓
  - [ ] Virtual environment exists ✓
  - [ ] Python3 available ✓
  - [ ] Git configured ✓
  - [ ] Workspace structure intact ✓
  - [ ] tmux config exists ✓
  - [ ] Backup script ready ✓

**Status:** ☐ Complete ☐ In Progress ☐ Not Started

---

## Phase 7: First Claude Code Session ☐

- [ ] Started tmux session: `tmux new -s claude-dev`
- [ ] Navigated to workspace: `cd /home/admin/.openclaw/workspace/auto-trade-system`
- [ ] Activated virtual environment: `source .venv/bin/activate`
- [ ] Launched Claude Code: `claude`
- [ ] Successfully asked first question
- [ ] Tested file reading capability
- [ ] Tested command execution capability
- [ ] Detached and reattached session successfully

**Status:** ☐ Complete ☐ In Progress ☐ Not Started

---

## Phase 8: Backup Configuration ☐

- [ ] Tested backup script: `./scripts/backup_workspace.sh`
- [ ] Verified backup created in `~/backups/auto-trade-system/`
- [ ] Checked backup contents (optional extraction test)
- [ ] Optional: Set up automated daily backup via cron:
  ```bash
  crontab -e
  # Add: 0 2 * * * /home/admin/.openclaw/workspace/auto-trade-system/scripts/backup_workspace.sh
  ```

**Status:** ☐ Complete ☐ In Progress ☐ Not Started

---

## Phase 9: Workflow Testing ☐

Tested Claude Code with these tasks:

### Code Analysis
- [ ] Asked Claude to analyze a module (e.g., "Review app/core/execution_engine.py")
- [ ] Received meaningful feedback

### Testing
- [ ] Asked Claude to help with tests (e.g., "Generate tests for app/risk_engine/")
- [ ] Successfully ran pytest through Claude

### Debugging
- [ ] Asked Claude to debug an issue
- [ ] Received actionable suggestions

### Refactoring
- [ ] Asked Claude for refactoring suggestions
- [ ] Understood the proposed improvements

**Status:** ☐ Complete ☐ In Progress ☐ Not Started

---

## Final Verification ☐

Before marking setup as complete, verify:

- [ ] Can start Claude Code from any terminal
- [ ] Virtual environment activates automatically or with simple command
- [ ] Tmux sessions persist after detachment
- [ ] Claude Code can read files in workspace
- [ ] Claude Code can run commands (pytest, etc.)
- [ ] Python imports work correctly inside Claude Code
- [ ] Backup script runs without errors
- [ ] Comfortable with basic tmux navigation

---

## Notes & Issues

Document any issues encountered and how they were resolved:

```
Date: ________
Issue: _______________________________________________________
Solution: ____________________________________________________
______________________________________________________________

Date: ________
Issue: _______________________________________________________
Solution: ____________________________________________________
______________________________________________________________

Date: ________
Issue: _______________________________________________________
Solution: ____________________________________________________
______________________________________________________________
```

---

## Completion Sign-off

- [ ] All phases completed
- [ ] All verification checks passed
- [ ] Comfortable with daily workflow
- [ ] Backup system configured
- [ ] Ready for productive use

**Completed by:** ___________________  
**Date:** ___________________  
**Signature:** ___________________

---

## Next Steps After Completion

Once this checklist is complete:

1. **Read** `CLAUDE_CODE_QUICKREF.md` for daily workflows
2. **Bookmark** troubleshooting section for future reference
3. **Explore** advanced tmux features for productivity
4. **Create** custom prompts for your specific trading system tasks
5. **Integrate** Claude Code into your regular development workflow

---

**Congratulations on setting up your AI-powered development environment! 🎉**
