#!/bin/bash
# Wrapper script to always enable debug mode for Claude Code
# This fixes the initialization timeout issue

export CLAUDE_DEBUG=true
exec $HOME/.npm-global/bin/claude "$@"
