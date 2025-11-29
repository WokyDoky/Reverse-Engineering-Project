#!/bin/bash
# setup_bt_hid.sh
# Setup script for Bluetooth HID keyboard on Raspberry Pi 5

set -e

echo "============================================"
echo "Bluetooth HID Keyboard Setup Script"
echo "For Raspberry Pi 5 with Raspberry Pi OS"
echo "============================================"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "[!] Please run as root: sudo bash setup_bt_hid.sh"
    exit 1
fi

echo "[*] Step 1: Installing dependencies..."
apt-get update
apt-get install -y bluez python3-dbus python3-gi python3-bluez bluez-tools

echo ""
echo "[*] Step 2: Backing up Bluetooth configuration..."
if [ ! -f /etc/bluetooth/main.conf.backup ]; then
    cp /etc/bluetooth/main.conf /etc/bluetooth/main.conf.backup
    echo "    Backup created: /etc/bluetooth/main.conf.backup"
else
    echo "    Backup already exists"
fi

echo ""
echo "[*] Step 3: Configuring Bluetooth..."

# Update main.conf
if ! grep -q "^Name = RPi5-Keyboard" /etc/bluetooth/main.conf; then
    echo "    Updating /etc/bluetooth/main.conf..."
    
    # Update or add settings in [General] section
    sed -i '/^\[General\]/a Name = RPi5-Keyboard' /etc/bluetooth/main.conf 2>/dev/null || true
    sed -i '/^\[General\]/a Class = 0x002540' /etc/bluetooth/main.conf 2>/dev/null || true
    sed -i '/^\[General\]/a DisablePlugins = input' /etc/bluetooth/main.conf 2>/dev/null || true
    sed -i '/^\[General\]/a DiscoverableTimeout = 0' /etc/bluetooth/main.conf 2>/dev/null || true
    sed -i '/^\[General\]/a PairableTimeout = 0' /etc/bluetooth/main.conf 2>/dev/null || true
    
    echo "    Configuration updated"
else
    echo "    Configuration already updated"
fi

echo ""
echo "[*] Step 4: Updating Bluetooth service..."

# Backup systemd service
if [ ! -f /lib/systemd/system/bluetooth.service.backup ]; then
    cp /lib/systemd/system/bluetooth.service /lib/systemd/system/bluetooth.service.backup
    echo "    Service backup created"
fi

# Update service to disable input plugin
if ! grep -q "noplugin=input" /lib/systemd/system/bluetooth.service; then
    sed -i 's|ExecStart=/usr/libexec/bluetooth/bluetoothd|ExecStart=/usr/libexec/bluetooth/bluetoothd --noplugin=input|g' /lib/systemd/system/bluetooth.service
    echo "    Service file updated"
else
    echo "    Service file already configured"
fi

echo ""
echo "[*] Step 5: Reloading systemd and restarting Bluetooth..."
systemctl daemon-reload
systemctl restart bluetooth

echo ""
echo "[*] Step 6: Verifying Bluetooth service..."
if systemctl is-active --quiet bluetooth; then
    echo "    [✓] Bluetooth service is running"
else
    echo "    [✗] Bluetooth service failed to start!"
    echo "    Check logs: sudo journalctl -u bluetooth -n 50"
    exit 1
fi

echo ""
echo "============================================"
echo "Setup Complete!"
echo "============================================"
echo ""
echo "Next steps:"
echo "1. Run diagnostic: sudo python3 bt_hid_diagnostic.py"
echo "2. Try the simple version: sudo python3 bt_hid_simple.py"
echo "3. Or try the fixed version: sudo python3 bt_hid_keyboard_fixed.py"
echo ""
echo "To monitor Bluetooth traffic:"
echo "  sudo btmon"
echo ""
echo "To restore original configuration:"
echo "  sudo cp /etc/bluetooth/main.conf.backup /etc/bluetooth/main.conf"
echo "  sudo cp /lib/systemd/system/bluetooth.service.backup /lib/systemd/system/bluetooth.service"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl restart bluetooth"
echo ""
