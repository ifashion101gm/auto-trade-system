#!/bin/bash
###############################################################################
# Claude Code Setup Verification Script
# Purpose: Verify all components are correctly installed and configured
# Usage: ./verify_claude_setup.sh
###############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

PASS_COUNT=0
FAIL_COUNT=0
TOTAL_CHECKS=0

check_pass() {
    echo -e "${GREEN}✓ PASS${NC}: $1"
    PASS_COUNT=$((PASS_COUNT + 1))
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
}

check_fail() {
    echo -e "${RED}✗ FAIL${NC}: $1"
    FAIL_COUNT=$((FAIL_COUNT + 1))
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
}

check_warn() {
    echo -e "${YELLOW}⚠ WARN${NC}: $1"
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
}

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Claude Code Setup Verification${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "Workspace: /home/admin/.openclaw/workspace/auto-trade-system"
echo "Date: $(date)"
echo ""

# Check 1: Node.js installation
echo -e "${BLUE}[Check 1/10] Node.js Installation${NC}"
if command -v node &> /dev/null; then
    NODE_VERSION=$(node -v)
    if [[ "$NODE_VERSION" =~ ^v22\. ]]; then
        check_pass "Node.js $NODE_VERSION installed (v22.x required)"
    else
        check_fail "Node.js version $NODE_VERSION found (v22.x required)"
    fi
else
    check_fail "Node.js not found in PATH"
fi
echo ""

# Check 2: npm installation
echo -e "${BLUE}[Check 2/10] npm Installation${NC}"
if command -v npm &> /dev/null; then
    NPM_VERSION=$(npm -v)
    check_pass "npm $NPM_VERSION installed"
else
    check_fail "npm not found in PATH"
fi
echo ""

# Check 3: Claude Code installation
echo -e "${BLUE}[Check 3/10] Claude Code Installation${NC}"
if command -v claude &> /dev/null; then
    CLAUDE_VERSION=$(timeout 3 claude --version 2>&1 | head -1 || echo "needs authentication")
    if [[ "$CLAUDE_VERSION" == *"timed out"* ]] || [[ -z "$CLAUDE_VERSION" ]]; then
        check_pass "Claude Code installed (authentication required)"
        echo -e "${YELLOW}  Run 'claude' to authenticate${NC}"
    else
        check_pass "Claude Code installed ($CLAUDE_VERSION)"
    fi
else
    check_fail "Claude Code not found in PATH"
    echo -e "${YELLOW}  Install with: npm install -g @anthropic-ai/claude-code${NC}"
fi
echo ""

# Check 4: tmux installation
echo -e "${BLUE}[Check 4/10] tmux Installation${NC}"
if command -v tmux &> /dev/null; then
    TMUX_VERSION=$(tmux -V)
    check_pass "tmux installed ($TMUX_VERSION)"
else
    check_fail "tmux not found in PATH"
    echo -e "${YELLOW}  Install with: sudo dnf install -y tmux (Alibaba Cloud Linux)${NC}"
    echo -e "${YELLOW}              or: sudo apt install -y tmux (Ubuntu/Debian)${NC}"
fi
echo ""

# Check 5: Python virtual environment
echo -e "${BLUE}[Check 5/10] Python Virtual Environment${NC}"
VENV_PATH="/home/admin/.openclaw/workspace/auto-trade-system/.venv"
if [ -d "$VENV_PATH" ]; then
    if [ -f "$VENV_PATH/bin/activate" ]; then
        check_pass "Virtual environment exists at .venv/"
    else
        check_fail "Virtual environment directory exists but activate script missing"
    fi
else
    check_fail "Virtual environment not found at .venv/"
    echo -e "${YELLOW}  Create with: python3 -m venv .venv${NC}"
fi
echo ""

# Check 6: Python3 availability
echo -e "${BLUE}[Check 6/10] Python3 Installation${NC}"
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    check_pass "Python3 available ($PYTHON_VERSION)"
else
    check_fail "Python3 not found in PATH"
fi
echo ""

# Check 7: Git configuration
echo -e "${BLUE}[Check 7/10] Git Configuration${NC}"
if command -v git &> /dev/null; then
    GIT_USER=$(git config user.name 2>/dev/null || echo "not set")
    GIT_EMAIL=$(git config user.email 2>/dev/null || echo "not set")
    if [ "$GIT_USER" != "not set" ] && [ "$GIT_EMAIL" != "not set" ]; then
        check_pass "Git configured ($GIT_USER <$GIT_EMAIL>)"
    else
        check_warn "Git not fully configured (user: $GIT_USER, email: $GIT_EMAIL)"
        echo -e "${YELLOW}  Configure with: git config --global user.name 'Your Name'${NC}"
        echo -e "${YELLOW}               git config --global user.email 'email@example.com'${NC}"
    fi
else
    check_fail "Git not found in PATH"
fi
echo ""

# Check 8: Workspace directory structure
echo -e "${BLUE}[Check 8/10] Workspace Directory Structure${NC}"
WORKSPACE="/home/admin/.openclaw/workspace/auto-trade-system"
REQUIRED_DIRS=("app" "scripts" "tests")
MISSING_DIRS=()

for dir in "${REQUIRED_DIRS[@]}"; do
    if [ ! -d "$WORKSPACE/$dir" ]; then
        MISSING_DIRS+=("$dir")
    fi
done

if [ ${#MISSING_DIRS[@]} -eq 0 ]; then
    check_pass "All required directories exist"
else
    check_fail "Missing directories: ${MISSING_DIRS[*]}"
fi
echo ""

# Check 9: tmux configuration file
echo -e "${BLUE}[Check 9/10] tmux Configuration${NC}"
if [ -f ~/.tmux.conf ]; then
    check_pass "tmux configuration exists (~/.tmux.conf)"
else
    check_warn "tmux configuration not found (~/.tmux.conf)"
    echo -e "${YELLOW}  Copy example from: $WORKSPACE/scripts/tmux.conf.example${NC}"
    echo -e "${YELLOW}  Command: cp $WORKSPACE/scripts/tmux.conf.example ~/.tmux.conf${NC}"
fi
echo ""

# Check 10: Backup script
echo -e "${BLUE}[Check 10/10] Backup Script${NC}"
BACKUP_SCRIPT="$WORKSPACE/scripts/backup_workspace.sh"
if [ -f "$BACKUP_SCRIPT" ]; then
    if [ -x "$BACKUP_SCRIPT" ]; then
        check_pass "Backup script exists and is executable"
    else
        check_warn "Backup script exists but is not executable"
        echo -e "${YELLOW}  Make executable: chmod +x $BACKUP_SCRIPT${NC}"
    fi
else
    check_warn "Backup script not found"
    echo -e "${YELLOW}  Create from: $WORKSPACE/scripts/backup_workspace.sh${NC}"
fi
echo ""

# Summary
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Verification Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "Total checks: $TOTAL_CHECKS"
echo -e "${GREEN}Passed: $PASS_COUNT${NC}"
echo -e "${RED}Failed: $FAIL_COUNT${NC}"
WARN_COUNT=$((TOTAL_CHECKS - PASS_COUNT - FAIL_COUNT))
if [ $WARN_COUNT -gt 0 ]; then
    echo -e "${YELLOW}Warnings: $WARN_COUNT${NC}"
fi
echo ""

if [ $FAIL_COUNT -eq 0 ]; then
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}✓ All critical checks passed!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "Your Claude Code setup is ready to use."
    echo ""
    echo "Next steps:"
    echo "1. Authenticate Claude Code: claude"
    echo "2. Start a tmux session: tmux new -s claude-dev"
    echo "3. Navigate to workspace: cd $WORKSPACE"
    echo "4. Activate venv: source .venv/bin/activate"
    echo "5. Run Claude Code: claude"
else
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}✗ Some checks failed${NC}"
    echo -e "${RED}========================================${NC}"
    echo ""
    echo "Please fix the failed checks above before proceeding."
    echo "Refer to CLAUDE_CODE_LOCAL_SETUP_PLAN.md for detailed instructions."
    exit 1
fi
