#!/bin/bash
###############################################################################
# Claude Code Session Starter for Auto-Trade-System
# Purpose: Quickly start a Claude Code session with proper environment setup
# Usage: ./scripts/start_claude_session.sh [session_name]
# Example: ./scripts/start_claude_session.sh claude-trading
###############################################################################

set -e  # Exit on error

# Configuration
WORKSPACE="/home/admin/.openclaw/workspace/auto-trade-system"
SESSION_NAME=${1:-"claude-trading"}
DEFAULT_EDITOR="vim"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Claude Code Session Starter${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if tmux is installed
if ! command -v tmux &> /dev/null; then
    echo -e "${RED}✗ ERROR: tmux is not installed${NC}"
    echo "Install with: sudo yum install -y tmux (Alibaba Cloud Linux)"
    echo "           or: sudo apt install -y tmux (Ubuntu/Debian)"
    exit 1
fi

# Check if Claude Code is installed
if ! command -v claude &> /dev/null; then
    echo -e "${RED}✗ ERROR: Claude Code is not installed${NC}"
    echo "Install with: npm install -g @anthropic-ai/claude-code"
    exit 1
fi

# Check if session already exists
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo -e "${YELLOW}⚠ Session '$SESSION_NAME' already exists${NC}"
    echo -e "${YELLOW}  Attaching to existing session...${NC}"
    echo ""
    tmux attach -t "$SESSION_NAME"
    exit 0
fi

echo -e "${GREEN}✓ Creating new session: $SESSION_NAME${NC}"
echo ""

# Create new detached session
tmux new-session -d -s "$SESSION_NAME" -x 200 -y 50

# Set up environment in the session
echo -e "${GREEN}✓ Configuring environment...${NC}"
tmux send-keys -t "$SESSION_NAME" "cd $WORKSPACE" C-m
tmux send-keys -t "$SESSION_NAME" "source .venv/bin/activate" C-m
tmux send-keys -t "$SESSION_NAME" "export PYTHONPATH=$WORKSPACE:\$PYTHONPATH" C-m
tmux send-keys -t "$SESSION_NAME" "export EDITOR=$DEFAULT_EDITOR" C-m

# Optional: Split window for monitoring (uncomment if desired)
# echo -e "${GREEN}✓ Setting up monitoring pane...${NC}"
# tmux split-window -h -t "$SESSION_NAME"
# tmux send-keys -t "$SESSION_NAME:0.1" "tail -f logs/app.log 2>/dev/null || echo 'No log file yet - start the app first'" C-m
# tmux select-pane -t "$SESSION_NAME:0.0"

# Rename window for clarity
tmux rename-window -t "$SESSION_NAME:0" "claude-dev"

echo -e "${GREEN}✓ Session ready!${NC}"
echo ""
echo -e "${BLUE}Session Details:${NC}"
echo -e "  Name:      ${GREEN}$SESSION_NAME${NC}"
echo -e "  Workspace: ${GREEN}$WORKSPACE${NC}"
echo -e "  Python:    ${GREEN}$(python3 --version 2>&1)${NC}"
echo -e "  Claude:    ${GREEN}$(claude --version 2>&1 | head -1)${NC}"
echo ""
echo -e "${BLUE}Quick Commands:${NC}"
echo -e "  Attach:    ${YELLOW}tmux attach -t $SESSION_NAME${NC}"
echo -e "  List:      ${YELLOW}tmux ls${NC}"
echo -e "  Kill:      ${YELLOW}tmux kill-session -t $SESSION_NAME${NC}"
echo ""
echo -e "${BLUE}Tmux Shortcuts:${NC}"
echo -e "  Detach:    ${YELLOW}CTRL+B then D${NC}"
echo -e "  Split H:   ${YELLOW}CTRL+B then %{NC}"
echo -e "  Split V:   ${YELLOW}CTRL+B then \"${NC}"
echo -e "  Next Pane: ${YELLOW}CTRL+B then Arrow${NC}"
echo -e "  Reload:    ${YELLOW}CTRL+B then r${NC}"
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Starting Claude Code...${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Attach to session and start Claude Code
tmux attach -t "$SESSION_NAME"
