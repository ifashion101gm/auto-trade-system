#!/bin/bash
#
# Auto Trade System - Deployment Script
# Provides options for running with or without systemd
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

WORKSPACE="/home/admin/.openclaw/workspace/auto-trade-system"
VENV_PYTHON="$WORKSPACE/.venv/bin/python"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Auto Trade System Deployment${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check if running as root for systemd operations
check_root() {
    if [[ $EUID -ne 0 ]]; then
        echo -e "${RED}Error: This operation requires sudo privileges${NC}"
        echo "Please run with: sudo $0"
        exit 1
    fi
}

# Option 1: Run manually (current method)
run_manual() {
    echo -e "${YELLOW}Starting application manually...${NC}"
    echo -e "This will run in the foreground. Press Ctrl+C to stop.\n"
    
    cd "$WORKSPACE"
    
    # Check if already running
    if pgrep -f "uvicorn app.main:app" > /dev/null; then
        echo -e "${RED}Application is already running!${NC}"
        echo "PID: $(pgrep -f 'uvicorn app.main:app')"
        echo ""
        echo "To restart, first stop it:"
        echo "  kill $(pgrep -f 'uvicorn app.main:app')"
        exit 1
    fi
    
    echo -e "${GREEN}Starting uvicorn on port 8000...${NC}"
    $VENV_PYTHON -m uvicorn app.main:app --host 0.0.0.0 --port 8000
}

# Option 2: Install systemd services
install_systemd() {
    check_root
    
    echo -e "${YELLOW}Installing systemd services...${NC}"
    
    # Copy service files
    cp "$WORKSPACE/systemd/auto-trade-api.service" /etc/systemd/system/
    cp "$WORKSPACE/systemd/auto-trade-worker.service" /etc/systemd/system/
    
    # Reload systemd
    systemctl daemon-reload
    
    # Enable services
    systemctl enable auto-trade-api
    systemctl enable auto-trade-worker
    
    echo -e "${GREEN}✅ Systemd services installed and enabled${NC}"
    echo ""
    echo "To start services:"
    echo "  sudo systemctl start auto-trade-api"
    echo "  sudo systemctl start auto-trade-worker"
    echo ""
    echo "To check status:"
    echo "  sudo systemctl status auto-trade-api"
    echo "  sudo systemctl status auto-trade-worker"
    echo ""
    echo "To view logs:"
    echo "  sudo journalctl -u auto-trade-api -f"
    echo "  sudo journalctl -u auto-trade-worker -f"
}

# Option 3: Start systemd services
start_systemd() {
    check_root
    
    echo -e "${YELLOW}Starting systemd services...${NC}"
    
    systemctl start auto-trade-api
    systemctl start auto-trade-worker
    
    echo -e "${GREEN}✅ Services started${NC}"
    echo ""
    echo "Check status with: sudo systemctl status auto-trade-api"
}

# Option 4: Stop systemd services
stop_systemd() {
    check_root
    
    echo -e "${YELLOW}Stopping systemd services...${NC}"
    
    systemctl stop auto-trade-api
    systemctl stop auto-trade-worker
    
    echo -e "${GREEN}✅ Services stopped${NC}"
}

# Option 5: Restart systemd services
restart_systemd() {
    check_root
    
    echo -e "${YELLOW}Restarting systemd services...${NC}"
    
    systemctl restart auto-trade-api
    systemctl restart auto-trade-worker
    
    echo -e "${GREEN}✅ Services restarted${NC}"
}

# Option 6: Uninstall systemd services
uninstall_systemd() {
    check_root
    
    echo -e "${YELLOW}Uninstalling systemd services...${NC}"
    
    systemctl stop auto-trade-api 2>/dev/null || true
    systemctl stop auto-trade-worker 2>/dev/null || true
    
    systemctl disable auto-trade-api 2>/dev/null || true
    systemctl disable auto-trade-worker 2>/dev/null || true
    
    rm -f /etc/systemd/system/auto-trade-api.service
    rm -f /etc/systemd/system/auto-trade-worker.service
    
    systemctl daemon-reload
    
    echo -e "${GREEN}✅ Services uninstalled${NC}"
}

# Show current status
show_status() {
    echo -e "${YELLOW}Current Status:${NC}"
    echo ""
    
    # Check if running manually
    if pgrep -f "uvicorn app.main:app" > /dev/null; then
        echo -e "${GREEN}● Running manually${NC}"
        echo "  PID: $(pgrep -f 'uvicorn app.main:app')"
    else
        echo -e "${RED}○ Not running manually${NC}"
    fi
    
    echo ""
    
    # Check systemd services
    if systemctl is-active --quiet auto-trade-api 2>/dev/null; then
        echo -e "${GREEN}● auto-trade-api.service: active${NC}"
    else
        echo -e "${RED}○ auto-trade-api.service: inactive${NC}"
    fi
    
    if systemctl is-active --quiet auto-trade-worker 2>/dev/null; then
        echo -e "${GREEN}● auto-trade-worker.service: active${NC}"
    else
        echo -e "${RED}○ auto-trade-worker.service: inactive${NC}"
    fi
    
    echo ""
    echo "Systemd services installed: $([ -f /etc/systemd/system/auto-trade-api.service ] && echo 'Yes' || echo 'No')"
}

# Main menu
show_menu() {
    echo "Select an option:"
    echo ""
    echo "  1) Run manually (foreground)"
    echo "  2) Install systemd services"
    echo "  3) Start systemd services"
    echo "  4) Stop systemd services"
    echo "  5) Restart systemd services"
    echo "  6) Uninstall systemd services"
    echo "  7) Show status"
    echo "  0) Exit"
    echo ""
    echo -n "Enter choice [0-7]: "
}

# Parse command line arguments
if [[ $# -gt 0 ]]; then
    case "$1" in
        --manual)
            run_manual
            ;;
        --install)
            install_systemd
            ;;
        --start)
            start_systemd
            ;;
        --stop)
            stop_systemd
            ;;
        --restart)
            restart_systemd
            ;;
        --uninstall)
            uninstall_systemd
            ;;
        --status)
            show_status
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Usage: $0 [--manual|--install|--start|--stop|--restart|--uninstall|--status]"
            exit 1
            ;;
    esac
else
    # Interactive mode
    while true; do
        show_status
        echo ""
        show_menu
        read -r choice
        
        case $choice in
            1) run_manual ;;
            2) install_systemd ;;
            3) start_systemd ;;
            4) stop_systemd ;;
            5) restart_systemd ;;
            6) uninstall_systemd ;;
            7) show_status ;;
            0) exit 0 ;;
            *) echo -e "${RED}Invalid option${NC}" ;;
        esac
        
        echo ""
        echo "Press Enter to continue..."
        read -r
    done
fi
