#!/bin/bash
# Quick Setup Script for Raspberry Pi 5 Bluetooth HID Keyboard
# Run with: sudo bash setup_pi5_hid.sh

set -e

echo "=========================================="
echo "Raspberry Pi 5 Bluetooth HID Setup"
echo "=========================================="
echo

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "ERROR: Please run as root (use sudo)"
    exit 1
fi

echo "[1/6] Installing required packages..."
apt update
apt install -y python3-dbus python3-gi bluez bluez-tools

echo
echo "[2/6] Backing up Bluetooth configuration..."
cp /etc/bluetooth/main.conf /etc/bluetooth/main.conf.backup 2>/dev/null || true

echo
echo "[3/6] Configuring Bluetooth for HID..."

# Check if configuration already exists
if grep -q "Class = 0x002540" /etc/bluetooth/main.conf; then
    echo "    Configuration already present, skipping..."
else
    # Add HID configuration to main.conf
    if grep -q "^\[General\]" /etc/bluetooth/main.conf; then
        # [General] section exists, add under it
        sed -i '/^\[General\]/a Class = 0x002540\nDisablePlugins = input' /etc/bluetooth/main.conf
    else
        # Add [General] section
        echo -e "\n[General]\nClass = 0x002540\nDisablePlugins = input" >> /etc/bluetooth/main.conf
    fi
    echo "    Configuration added successfully"
fi

echo
echo "[4/6] Configuring Bluetooth service for compatibility mode..."

# Backup the service file
cp /lib/systemd/system/bluetooth.service /lib/systemd/system/bluetooth.service.backup

# Modify ExecStart line to add -C flag
sed -i 's|^ExecStart=/usr/libexec/bluetooth/bluetoothd|ExecStart=/usr/libexec/bluetooth/bluetoothd -C|' /lib/systemd/system/bluetooth.service

echo
echo "[5/6] Reloading systemd and restarting Bluetooth..."
systemctl daemon-reload
systemctl restart bluetooth

# Wait for Bluetooth to stabilize
sleep 2

echo
echo "[6/6] Verifying Bluetooth status..."
if systemctl is-active --quiet bluetooth; then
    echo "    ✓ Bluetooth service is running"
else
    echo "    ✗ WARNING: Bluetooth service is not running"
    echo "    Check status with: sudo systemctl status bluetooth"
fi

# Ensure Bluetooth is unblocked
rfkill unblock bluetooth 2>/dev/null || true

echo
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo
echo "Next steps:"
echo "1. Make the script executable:"
echo "   chmod +x bt_hid_keyboard.py"
echo
echo "2. Run the keyboard script:"
echo "   sudo python3 bt_hid_keyboard.py"
echo
echo "3. On your Android device:"
echo "   - Go to Settings → Bluetooth"
echo "   - Scan for devices"
echo "   - Connect to 'RPi Keyboard'"
echo
echo "For detailed instructions, see SETUP_GUIDE.md"
echo

# Display Bluetooth adapter info
echo "Current Bluetooth Adapter Info:"
hciconfig 2>/dev/null || echo "Use 'bluetoothctl show' to view adapter details"
