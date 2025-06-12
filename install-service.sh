#!/bin/bash
#
# NFC Reader Service Installation Script
# Installs and configures the NFC reader as a systemd service
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="nfc-reader"
SERVICE_FILE="${SERVICE_NAME}.service"

echo -e "${GREEN}NFC Reader Service Installation${NC}"
echo "=================================="

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}Error: This script must be run as root${NC}"
   echo "Usage: sudo $0 [install|uninstall|status]"
   exit 1
fi

# Function to install service
install_service() {
    echo -e "${YELLOW}Installing NFC Reader Service...${NC}"
    
    # Check if service file exists
    if [[ ! -f "$SCRIPT_DIR/$SERVICE_FILE" ]]; then
        echo -e "${RED}Error: Service file $SERVICE_FILE not found${NC}"
        exit 1
    fi
    
    # Check if Python virtual environment exists
    if [[ ! -d "$SCRIPT_DIR/nfc_env" ]]; then
        echo -e "${RED}Error: Python virtual environment not found${NC}"
        echo "Please run: python3 -m venv nfc_env && source nfc_env/bin/activate && pip install -r requirements.txt"
        exit 1
    fi
    
    # Check if config exists
    if [[ ! -f "$SCRIPT_DIR/config.yaml" ]]; then
        echo -e "${YELLOW}Warning: config.yaml not found. Copy from config.yaml.template and configure${NC}"
    fi
    
    # Create log directory
    mkdir -p /var/log/nfc-reader
    chown root:root /var/log/nfc-reader
    chmod 755 /var/log/nfc-reader
    
    # Copy service file to systemd directory with path substitution
    sed "s|INSTALL_PATH|$SCRIPT_DIR|g" "$SCRIPT_DIR/$SERVICE_FILE" > "/etc/systemd/system/$SERVICE_FILE"
    # Remove ProtectHome=true to allow access to user directories
    sed -i '/ProtectHome=true/d' "/etc/systemd/system/$SERVICE_FILE"
    chmod 644 "/etc/systemd/system/$SERVICE_FILE"
    
    # Make service script executable
    chmod +x "$SCRIPT_DIR/nfc_reader_service.py"
    
    # Reload systemd daemon
    systemctl daemon-reload
    
    # Enable service
    systemctl enable "$SERVICE_NAME"
    
    echo -e "${GREEN}✅ Service installed successfully${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Configure config.yaml with your Home Assistant settings"
    echo "2. Start the service: sudo systemctl start $SERVICE_NAME"
    echo "3. Check status: sudo systemctl status $SERVICE_NAME"
    echo "4. View logs: sudo journalctl -u $SERVICE_NAME -f"
}

# Function to uninstall service
uninstall_service() {
    echo -e "${YELLOW}Uninstalling NFC Reader Service...${NC}"
    
    # Stop service
    systemctl stop "$SERVICE_NAME" 2>/dev/null || true
    
    # Disable service
    systemctl disable "$SERVICE_NAME" 2>/dev/null || true
    
    # Remove service file
    rm -f "/etc/systemd/system/$SERVICE_FILE"
    
    # Reload systemd daemon
    systemctl daemon-reload
    
    echo -e "${GREEN}✅ Service uninstalled successfully${NC}"
    echo "Log files in /var/log/nfc-reader have been preserved"
}

# Function to show service status
show_status() {
    echo -e "${YELLOW}NFC Reader Service Status:${NC}"
    echo ""
    
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        echo -e "Status: ${GREEN}Active (Running)${NC}"
    else
        echo -e "Status: ${RED}Inactive${NC}"
    fi
    
    if systemctl is-enabled --quiet "$SERVICE_NAME"; then
        echo -e "Enabled: ${GREEN}Yes${NC}"
    else
        echo -e "Enabled: ${RED}No${NC}"
    fi
    
    echo ""
    echo "Detailed status:"
    systemctl status "$SERVICE_NAME" --no-pager || true
    
    echo ""
    echo "Recent logs:"
    journalctl -u "$SERVICE_NAME" -n 10 --no-pager || true
}

# Main script logic
case "${1:-install}" in
    install)
        install_service
        ;;
    uninstall)
        uninstall_service
        ;;
    status)
        show_status
        ;;
    *)
        echo "Usage: $0 [install|uninstall|status]"
        echo ""
        echo "Commands:"
        echo "  install   - Install and enable the NFC reader service"
        echo "  uninstall - Stop and remove the NFC reader service"
        echo "  status    - Show current service status and recent logs"
        exit 1
        ;;
esac