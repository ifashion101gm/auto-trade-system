#!/bin/bash
###############################################################################
# Claude Code Fix - Apply Debug Mode and Optimize Startup
# Purpose: Resolve "Subprocess initialization did not complete within 60000ms"
# Root Cause: Claude hangs during non-debug initialization (likely telemetry/logging)
###############################################################################

set -e

echo "=========================================="
echo "Claude Code Fix - Applying Configuration"
echo "=========================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Step 1: Verify Claude is installed
echo -e "${BLUE}[Step 1] Verifying Claude installation...${NC}"
if ! command -v claude &> /dev/null; then
    echo -e "${RED}✗ ERROR: Claude Code is not installed${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Claude is installed${NC}"
echo ""

# Step 2: Test with debug mode (should work)
echo -e "${BLUE}[Step 2] Testing Claude with debug mode...${NC}"
if timeout 5 env CLAUDE_DEBUG=true claude --version > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Claude works with CLAUDE_DEBUG=true${NC}"
else
    echo -e "${RED}✗ Claude fails even with debug mode${NC}"
    exit 1
fi
echo ""

# Step 3: Test without debug mode (likely hangs)
echo -e "${BLUE}[Step 3] Testing Claude without debug mode...${NC}"
if timeout 3 claude --version > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Claude works without debug mode (unexpected!)${NC}"
else
    echo -e "${YELLOW}⚠ Claude hangs without debug mode (expected - this is the bug)${NC}"
fi
echo ""

# Step 4: Create wrapper script for Claude
echo -e "${BLUE}[Step 4] Creating Claude wrapper with debug mode...${NC}"

WRAPPER_SCRIPT="$HOME/.local/bin/claude-wrapper"
mkdir -p "$HOME/.local/bin"

cat > "$WRAPPER_SCRIPT" << 'EOF'
#!/bin/bash
# Wrapper script to always enable debug mode for Claude Code
# This fixes the initialization timeout issue

export CLAUDE_DEBUG=true
exec $HOME/.npm-global/bin/claude "$@"
EOF

chmod +x "$WRAPPER_SCRIPT"
echo -e "${GREEN}✓ Created wrapper script at $WRAPPER_SCRIPT${NC}"
echo ""

# Step 5: Update VSCode settings to use wrapper
echo -e "${BLUE}[Step 5] Configuring VSCode to use wrapper...${NC}"

VSCODE_SETTINGS="$HOME/.openclaw/workspace/auto-trade-system/.vscode/settings.json"
mkdir -p "$(dirname "$VSCODE_SETTINGS")"

# Check if settings file exists
if [ -f "$VSCODE_SETTINGS" ]; then
    # Add or update the claude path setting
    if grep -q "claudeCode.cliPath" "$VSCODE_SETTINGS"; then
        sed -i "s|\"claudeCode.cliPath\":.*|\"claudeCode.cliPath\": \"$WRAPPER_SCRIPT\",|" "$VSCODE_SETTINGS"
    else
        # Add the setting before the closing brace
        sed -i "s/}$/,\n  \"claudeCode.cliPath\": \"$WRAPPER_SCRIPT\"\n}/" "$VSCODE_SETTINGS"
    fi
    echo -e "${GREEN}✓ Updated VSCode settings${NC}"
else
    # Create new settings file
    cat > "$VSCODE_SETTINGS" << EOF
{
  "claudeCode.cliPath": "$WRAPPER_SCRIPT"
}
EOF
    echo -e "${GREEN}✓ Created VSCode settings file${NC}"
fi
echo ""

# Step 6: Set environment variable globally (optional)
echo -e "${BLUE}[Step 6] Setting CLAUDE_DEBUG in shell profile...${NC}"

SHELL_PROFILE="$HOME/.bashrc"
if ! grep -q "CLAUDE_DEBUG=true" "$SHELL_PROFILE"; then
    echo "" >> "$SHELL_PROFILE"
    echo "# Fix for Claude Code initialization timeout" >> "$SHELL_PROFILE"
    echo "export CLAUDE_DEBUG=true" >> "$SHELL_PROFILE"
    echo -e "${GREEN}✓ Added CLAUDE_DEBUG=true to $SHELL_PROFILE${NC}"
else
    echo -e "${YELLOW}⚠ CLAUDE_DEBUG already set in $SHELL_PROFILE${NC}"
fi
echo ""

# Step 7: Kill existing Claude processes
echo -e "${BLUE}[Step 7] Cleaning up existing Claude processes...${NC}"
pkill -f "claude --output-format stream-json" 2>/dev/null || true
sleep 1
echo -e "${GREEN}✓ Killed existing Claude processes${NC}"
echo ""

# Step 8: Test the fix
echo -e "${BLUE}[Step 8] Testing the fix...${NC}"
echo "Testing wrapper script..."
if timeout 5 "$WRAPPER_SCRIPT" --version > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Wrapper script works!${NC}"
else
    echo -e "${RED}✗ Wrapper script failed${NC}"
    exit 1
fi
echo ""

# Summary
echo "=========================================="
echo -e "${GREEN}✓ Fix Applied Successfully!${NC}"
echo "=========================================="
echo ""
echo "What was done:"
echo "1. Created wrapper script that enables CLAUDE_DEBUG=true"
echo "2. Updated VSCode settings to use the wrapper"
echo "3. Added CLAUDE_DEBUG to your shell profile"
echo "4. Cleaned up existing Claude processes"
echo ""
echo "Next steps:"
echo "1. Reload VSCode completely (close all windows)"
echo "2. Reopen your workspace"
echo "3. Try using Claude Code again"
echo ""
echo "If issues persist:"
echo "- Check VSCode Output panel for Claude Code logs"
echo "- Run 'source ~/.bashrc' in terminal to reload environment"
echo "- Verify wrapper is being used: which claude"
echo ""
echo "Wrapper location: $WRAPPER_SCRIPT"
echo "VSCode settings: $VSCODE_SETTINGS"
echo ""
