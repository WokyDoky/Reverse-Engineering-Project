#!/bin/bash
# Bluetooth HID Diagnostic Tool
# Helps diagnose common Bluetooth issues on Raspberry Pi 5

echo "╔════════════════════════════════════════════════════════════╗"
echo "║     Bluetooth HID Diagnostic Tool - Raspberry Pi 5        ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

echo "════════════════════════════════════════════════════════════"
echo " 1. CHECKING BLUETOOTH HARDWARE"
echo "════════════════════════════════════════════════════════════"

# Check if Bluetooth hardware is present
if [ -d "/sys/class/bluetooth" ]; then
    success "Bluetooth hardware detected"
    
    # List Bluetooth devices
    info "Bluetooth devices:"
    ls -1 /sys/class/bluetooth/
else
    error "No Bluetooth hardware found"
fi

echo

# Check rfkill status
info "Checking rfkill status..."
if command -v rfkill &> /dev/null; then
    rfkill list bluetooth
    
    if rfkill list bluetooth | grep -q "Soft blocked: yes"; then
        warning "Bluetooth is soft-blocked"
        echo "      Run: sudo rfkill unblock bluetooth"
    else
        success "Bluetooth is not blocked"
    fi
else
    warning "rfkill command not found"
fi

echo
echo "════════════════════════════════════════════════════════════"
echo " 2. BLUETOOTH SERVICE STATUS"
echo "════════════════════════════════════════════════════════════"

if systemctl is-active --quiet bluetooth; then
    success "Bluetooth service is ACTIVE"
else
    error "Bluetooth service is NOT active"
    echo "      Run: sudo systemctl start bluetooth"
fi

if systemctl is-enabled --quiet bluetooth; then
    success "Bluetooth service is ENABLED (starts at boot)"
else
    warning "Bluetooth service is not enabled"
    echo "      Run: sudo systemctl enable bluetooth"
fi

echo
info "Bluetooth service details:"
systemctl status bluetooth --no-pager -l | head -15

echo
echo "════════════════════════════════════════════════════════════"
echo " 3. BLUETOOTH ADAPTER INFORMATION"
echo "════════════════════════════════════════════════════════════"

if command -v hciconfig &> /dev/null; then
    info "Using hciconfig:"
    hciconfig -a
    echo
fi

if command -v bluetoothctl &> /dev/null; then
    info "Using bluetoothctl:"
    timeout 3 bluetoothctl show 2>/dev/null || echo "Timeout or error"
else
    error "bluetoothctl not found"
fi

echo
echo "════════════════════════════════════════════════════════════"
echo " 4. BLUETOOTH CONFIGURATION FILES"
echo "════════════════════════════════════════════════════════════"

# Check main.conf
if [ -f "/etc/bluetooth/main.conf" ]; then
    success "/etc/bluetooth/main.conf exists"
    
    if grep -q "Class = 0x002540" /etc/bluetooth/main.conf; then
        success "HID Device Class is configured (0x002540)"
    else
        warning "HID Device Class NOT configured"
        echo "      Add to [General] section: Class = 0x002540"
    fi
    
    if grep -q "DisablePlugins.*input" /etc/bluetooth/main.conf; then
        success "Input plugin is disabled (correct for manual HID)"
    else
        warning "Input plugin may not be disabled"
        echo "      Add to [General] section: DisablePlugins = input"
    fi
    
    echo
    info "Current [General] section:"
    sed -n '/^\[General\]/,/^\[/p' /etc/bluetooth/main.conf | head -20
else
    error "/etc/bluetooth/main.conf not found"
fi

echo
echo "════════════════════════════════════════════════════════════"
echo " 5. BLUETOOTH SERVICE CONFIGURATION"
echo "════════════════════════════════════════════════════════════"

if [ -f "/lib/systemd/system/bluetooth.service" ]; then
    success "Bluetooth service file exists"
    
    if grep -q "bluetoothd -C" /lib/systemd/system/bluetooth.service; then
        success "Compatibility mode (-C flag) is enabled"
    else
        warning "Compatibility mode (-C flag) NOT enabled"
        echo "      Modify ExecStart line to: ExecStart=/usr/libexec/bluetooth/bluetoothd -C"
    fi
    
    echo
    info "ExecStart line:"
    grep "ExecStart=" /lib/systemd/system/bluetooth.service
else
    error "Bluetooth service file not found"
fi

echo
echo "════════════════════════════════════════════════════════════"
echo " 6. PYTHON DEPENDENCIES"
echo "════════════════════════════════════════════════════════════"

# Check Python3
if command -v python3 &> /dev/null; then
    version=$(python3 --version 2>&1)
    success "Python3 installed: $version"
else
    error "Python3 not found"
fi

# Check dbus
if python3 -c "import dbus" 2>/dev/null; then
    success "python3-dbus is installed"
else
    error "python3-dbus is NOT installed"
    echo "      Run: sudo apt install python3-dbus"
fi

# Check gi
if python3 -c "import gi; gi.require_version('GLib', '2.0'); from gi.repository import GLib" 2>/dev/null; then
    success "python3-gi (GLib) is installed"
else
    error "python3-gi is NOT installed"
    echo "      Run: sudo apt install python3-gi"
fi

echo
echo "════════════════════════════════════════════════════════════"
echo " 7. BLUETOOTH L2CAP SOCKETS"
echo "════════════════════════════════════════════════════════════"

info "Checking L2CAP module..."
if lsmod | grep -q "^l2cap"; then
    success "L2CAP module is loaded"
else
    warning "L2CAP module not found"
    echo "      Try: sudo modprobe l2cap"
fi

info "Checking Bluetooth sockets..."
if [ -f "/proc/net/l2cap" ]; then
    success "/proc/net/l2cap exists"
    
    if [ -s "/proc/net/l2cap" ]; then
        info "Active L2CAP connections:"
        cat /proc/net/l2cap | head -20
    else
        info "No active L2CAP connections"
    fi
else
    warning "/proc/net/l2cap not found"
fi

echo
echo "════════════════════════════════════════════════════════════"
echo " 8. BLUETOOTH MAC ADDRESS"
echo "════════════════════════════════════════════════════════════"

if command -v hciconfig &> /dev/null; then
    MAC=$(hciconfig hci0 2>/dev/null | grep "BD Address" | awk '{print $3}')
    if [ -n "$MAC" ]; then
        success "Bluetooth MAC Address: $MAC"
    else
        warning "Could not get MAC address via hciconfig"
    fi
fi

# Alternative method
if command -v bluetoothctl &> /dev/null; then
    info "Getting address via bluetoothctl..."
    timeout 2 bluetoothctl show 2>/dev/null | grep "Address"
fi

echo
echo "════════════════════════════════════════════════════════════"
echo " 9. KERNEL VERSION AND BLUETOOTH FIRMWARE"
echo "════════════════════════════════════════════════════════════"

info "Kernel version:"
uname -r

info "Checking for Bluetooth firmware..."
if [ -d "/lib/firmware/brcm" ]; then
    success "Broadcom firmware directory exists"
    ls -lh /lib/firmware/brcm/ | grep -i "BCM.*\.hcd" | head -5
else
    warning "Broadcom firmware directory not found"
fi

echo
echo "════════════════════════════════════════════════════════════"
echo " 10. RECOMMENDATIONS"
echo "════════════════════════════════════════════════════════════"

problems=0

# Check for common issues
if ! systemctl is-active --quiet bluetooth; then
    error "Bluetooth service not running"
    echo "      → sudo systemctl start bluetooth"
    ((problems++))
fi

if ! grep -q "Class = 0x002540" /etc/bluetooth/main.conf 2>/dev/null; then
    warning "HID class not configured"
    echo "      → Run: sudo bash setup_pi5_hid.sh"
    ((problems++))
fi

if ! python3 -c "import dbus" 2>/dev/null; then
    error "python3-dbus not installed"
    echo "      → sudo apt install python3-dbus python3-gi"
    ((problems++))
fi

if rfkill list bluetooth 2>/dev/null | grep -q "Soft blocked: yes"; then
    error "Bluetooth is blocked"
    echo "      → sudo rfkill unblock bluetooth"
    ((problems++))
fi

if [ $problems -eq 0 ]; then
    echo
    success "════════════════════════════════════════════════════════"
    success "  No critical issues found! System appears ready."
    success "════════════════════════════════════════════════════════"
    echo
    info "To run the HID keyboard script:"
    echo "    sudo python3 bt_hid_keyboard.py"
else
    echo
    warning "════════════════════════════════════════════════════════"
    warning "  Found $problems issue(s) - please fix before running"
    warning "════════════════════════════════════════════════════════"
    echo
    info "For automated setup, run:"
    echo "    sudo bash setup_pi5_hid.sh"
fi

echo
info "Diagnostic complete!"
