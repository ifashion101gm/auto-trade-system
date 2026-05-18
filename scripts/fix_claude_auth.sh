#!/bin/bash
###############################################################################
# Fix Claude Code Authentication Issue
# Purpose: Resolve "Subprocess initialization did not complete within 60000ms"
###############################################################################

set -e

echo "=========================================="
echo "Claude Code Authentication Fix"
echo "=========================================="
echo ""

# Check if claude is installed
if ! command -v claude &> /dev/null; then
    echo "❌ ERROR: Claude Code is not installed"
    echo "Install with: npm install -g @anthropic-ai/claude-code"
    exit 1
fi

echo "✓ Claude Code is installed"
echo ""

# Check for existing authentication
if [ -d ~/.claude ]; then
    echo "✓ Found ~/.claude directory"
    if [ -f ~/.claude/credentials.json ] || [ -f ~/.claude/auth.json ]; then
        echo "✓ Authentication tokens found"
        echo ""
        echo "Testing authentication..."
        timeout 5 claude --version > /dev/null 2>&1 && echo "✓ Authentication is valid" || echo "⚠ Authentication may be expired"
    else
        echo "⚠ No authentication tokens found in ~/.claude"
    fi
else
    echo "⚠ No ~/.claude directory found (not authenticated yet)"
fi

echo ""
echo "=========================================="
echo "Authentication Steps:"
echo "=========================================="
echo ""
echo "1. Run this command in your terminal:"
echo "   claude login"
echo ""
echo "2. A browser window will open for OAuth authentication"
echo "   Complete the sign-in process with your Anthropic account"
echo ""
echo "3. After successful authentication, verify with:"
echo "   claude --version"
echo ""
echo "4. Restart VSCode completely"
echo ""
echo "5. Try using Claude Code in VSCode again"
echo ""
echo "=========================================="
echo ""

# Optional: Auto-start authentication
read -p "Do you want to start authentication now? (y/n): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Starting Claude Code authentication..."
    echo "A browser window should open shortly..."
    echo ""
    claude login
else
    echo "Skipping automatic authentication. Please run 'claude login' manually."
fi
