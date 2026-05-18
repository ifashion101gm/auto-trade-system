# Claude Code Installation - Alibaba Cloud Linux 3

**System:** Alibaba Cloud Linux 3.2104 (OpenAnolis Edition)  
**Based on:** RHEL/CentOS 8  
**Package Manager:** `yum` or `dnf` (NOT `apt`)  
**Date:** May 17, 2026

---

## ✅ Current Status

- ✅ Node.js v22.22.2 - **Already Installed**
- ✅ npm 10.9.7 - **Already Installed**
- ✅ Claude Code 2.1.143 - **Installed** (user-level npm)
- ⚠️ tmux - **Not yet installed** (see instructions below)
- ✅ Git - Should be available

---

## 🚀 Quick Installation (Completed Steps)

### What Was Done

1. **Configured user-level npm** (to avoid permission issues):
   ```bash
   mkdir -p ~/.npm-global
   npm config set prefix '~/.npm-global'
   echo 'export PATH=~/.npm-global/bin:$PATH' >> ~/.bashrc
   source ~/.bashrc
   ```

2. **Installed Claude Code**:
   ```bash
   npm install -g @anthropic-ai/claude-code
   ```

3. **Verified installation**:
   ```bash
   claude --version
   # Output: 2.1.143 (Claude Code)
   ```

---

## 📦 Installing Missing Dependencies

### Install tmux (Required for Persistent Sessions)

**Option 1: Using dnf (recommended)**
```bash
sudo dnf install -y tmux
```

**Option 2: Using yum**
```bash
sudo yum install -y tmux
```

**Option 3: Using Linuxbrew (if dnf/yum don't work)**
```bash
brew install tmux
```

**Verify installation:**
```bash
tmux -V
```

### Install Git (if not already installed)

```bash
sudo dnf install -y git
# or
sudo yum install -y git
```

**Verify:**
```bash
git --version
```

---

## 🔐 Authenticate Claude Code

Run this command and follow the browser authentication flow:

```bash
claude
```

This will:
1. Display an authentication link
2. Open your browser (or copy the link manually)
3. Log in with your Anthropic account
4. Complete OAuth authorization
5. Return to terminal - you're now authenticated!

---

## 🎯 Start Using Claude Code

### Without tmux (Basic Usage)
```bash
cd /home/admin/.openclaw/workspace/auto-trade-system
source .venv/bin/activate
claude
```

### With tmux (Recommended for Long Sessions)
After installing tmux:

```bash
# Start a new tmux session
tmux new -s claude-dev

# Navigate to project
cd /home/admin/.openclaw/workspace/auto-trade-system

# Activate virtual environment
source .venv/bin/activate

# Launch Claude Code
claude

# Detach safely: Press CTRL+B then D
# Reattach later: tmux attach -t claude-dev
```

---

## 🔧 System-Specific Notes

### Package Manager Differences

| Task | Ubuntu/Debian | Alibaba Cloud Linux (RHEL) |
|------|---------------|----------------------------|
| Update packages | `apt update` | `sudo dnf check-update` |
| Install package | `apt install pkg` | `sudo dnf install -y pkg` |
| Search package | `apt search pkg` | `dnf search pkg` |
| Remove package | `apt remove pkg` | `sudo dnf remove pkg` |

### Common Packages Installation

```bash
# Development tools
sudo dnf groupinstall -y "Development Tools"

# Specific packages
sudo dnf install -y curl git tmux htop unzip build-essential

# Python packages (if needed)
sudo dnf install -y python3 python3-pip python3-devel
```

---

## ⚠️ Troubleshooting

### Issue: "command not found: claude"

**Solution:** Ensure npm global bin is in PATH:
```bash
echo $PATH | grep npm-global

# If not found, add it:
export PATH=~/.npm-global/bin:$PATH
echo 'export PATH=~/.npm-global/bin:$PATH' >> ~/.bashrc
source ~/.bashrc
```

### Issue: dnf/yum permission denied

**Solution:** Use `sudo`:
```bash
sudo dnf install -y tmux
```

### Issue: Package not found in repositories

**Solution:** Enable additional repositories:
```bash
# Enable EPEL repository (Extra Packages for Enterprise Linux)
sudo dnf install -y epel-release

# Then try installing again
sudo dnf install -y tmux
```

### Issue: Slow package downloads

**Solution:** Update repository cache:
```bash
sudo dnf clean all
sudo dnf makecache
sudo dnf install -y tmux
```

---

## 📋 Verification Checklist

Run these commands to verify your setup:

```bash
# Check Node.js
node -v          # Should show v22.x.x

# Check npm
npm -v           # Should show 10.x.x

# Check Claude Code
claude --version # Should show 2.1.x

# Check tmux (after installation)
tmux -V          # Should show version

# Check git
git --version    # Should show version

# Check Python venv
cd /home/admin/.openclaw/workspace/auto-trade-system
source .venv/bin/activate
python3 --version
```

Or run the automated verification script:
```bash
./scripts/verify_claude_setup.sh
```

---

## 🔄 Next Steps

1. **Install tmux** (see instructions above)
2. **Authenticate Claude Code**: Run `claude`
3. **Configure tmux** (optional): `cp scripts/tmux.conf.example ~/.tmux.conf`
4. **Start your first session**: See usage instructions above
5. **Set up backups**: `./scripts/backup_workspace.sh`

---

## 📚 Additional Resources

- **Full Setup Plan:** [CLAUDE_CODE_LOCAL_SETUP_PLAN.md](CLAUDE_CODE_LOCAL_SETUP_PLAN.md)
- **Quick Reference:** [CLAUDE_CODE_QUICKREF.md](CLAUDE_CODE_QUICKREF.md)
- **Setup Summary:** [CLAUDE_CODE_SETUP_SUMMARY.md](CLAUDE_CODE_SETUP_SUMMARY.md)
- **Installation Checklist:** [CLAUDE_CODE_SETUP_CHECKLIST.md](CLAUDE_CODE_SETUP_CHECKLIST.md)

---

## 💡 Key Takeaways for Alibaba Cloud Linux

1. **Use `dnf` or `yum`**, NOT `apt`
2. **Node.js is already installed** (v22.22.2)
3. **Use user-level npm** to avoid permission issues
4. **Claude Code is successfully installed** at `~/.npm-global/bin/claude`
5. **tmux needs to be installed** separately using dnf/yum

---

**Your Claude Code setup is almost complete! Just install tmux and authenticate.** 🚀
