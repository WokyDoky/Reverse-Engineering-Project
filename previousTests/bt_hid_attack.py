#!/usr/bin/env python3
import os
import sys
import time
import socket
import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib

# --- Constants & Configuration ---
P_CTRL = 17  # HID Control Channel
P_INTR = 19  # HID Interrupt Channel
PROFILE_DBUS_PATH = "/bluez/yourservice/profile"
SDP_RECORD_XML = """
<record>
    <attribute id="0x0001">
        <sequence>
            <uuid value="00001124-0000-1000-8000-00805f9b34fb"/>
        </sequence>
    </attribute>
    <attribute id="0x0004">
        <sequence>
            <sequence>
                <uuid value="0x0100"/>
            </sequence>
            <sequence>
                <uuid value="0x0011"/>
            </sequence>
            <sequence>
                <uuid value="0x0013"/>
            </sequence>
        </sequence>
    </attribute>
    <attribute id="0x0006">
        <sequence>
            <uint16 value="0x0100"/>
            <uint16 value="0x0011"/>
            <uint16 value="0x0100"/>
            <uint16 value="0x0013"/>
        </sequence>
    </attribute>
    <attribute id="0x0009">
        <sequence>
            <uuid value="0x1124"/>
            <uint16 value="0x0100"/>
        </sequence>
    </attribute>
    <attribute id="0x000d">
        <sequence>
            <sequence>
                <sequence>
                    <uuid value="0x0100"/>
                    <uint16 value="0x0100"/>
                </sequence>
                <sequence>
                    <uuid value="0x0011"/>
                </sequence>
                <sequence>
                    <uuid value="0x0013"/>
                </sequence>
            </sequence>
        </sequence>
    </attribute>
    <attribute id="0x0100">
        <text value="Raspberry Pi 5 HID"/>
    </attribute>
    <attribute id="0x0101">
        <text value="Keyboard"/>
    </attribute>
    <attribute id="0x0201">
        <uint16 value="0x0100"/>
    </attribute>
</record>
"""

# --- HID Report Descriptor ---
# This describes a composite device: Keyboard (Report ID 1) + Consumer Control (Report ID 2)
# We need Consumer Control to send "Home" and "Search"
HID_REPORT_DESC = [
    0x05, 0x01,        # Usage Page (Generic Desktop)
    0x09, 0x06,        # Usage (Keyboard)
    0xA1, 0x01,        # Collection (Application)
    0x85, 0x01,        #   Report ID (1) - Standard Keyboard
    0x05, 0x07,        #   Usage Page (Keyboard)
    0x19, 0xE0,        #   Usage Minimum (224)
    0x29, 0xE7,        #   Usage Maximum (231)
    0x15, 0x00,        #   Logical Minimum (0)
    0x25, 0x01,        #   Logical Maximum (1)
    0x75, 0x01,        #   Report Size (1)
    0x95, 0x08,        #   Report Count (8)
    0x81, 0x02,        #   Input (Data, Variable, Absolute) - Modifiers
    0x95, 0x01,        #   Report Count (1)
    0x75, 0x08,        #   Report Size (8)
    0x81, 0x01,        #   Input (Constant) - Reserved byte
    0x95, 0x06,        #   Report Count (6)
    0x75, 0x08,        #   Report Size (8)
    0x15, 0x00,        #   Logical Minimum (0)
    0x25, 0x65,        #   Logical Maximum (101)
    0x05, 0x07,        #   Usage Page (Key Codes)
    0x19, 0x00,        #   Usage Minimum (0)
    0x29, 0x65,        #   Usage Maximum (101)
    0x81, 0x00,        #   Input (Data, Array) - Key arrays
    0xC0,              # End Collection (Keyboard)

    0x05, 0x0C,        # Usage Page (Consumer)
    0x09, 0x01,        # Usage (Consumer Control)
    0xA1, 0x01,        # Collection (Application)
    0x85, 0x02,        #   Report ID (2) - Consumer Control
    0x05, 0x0C,        #   Usage Page (Consumer)
    0x15, 0x00,        #   Logical Minimum (0)
    0x26, 0xFF, 0x03,  #   Logical Maximum (1023)
    0x19, 0x00,        #   Usage Minimum (0)
    0x2A, 0xFF, 0x03,  #   Usage Maximum (1023)
    0x75, 0x10,        #   Report Size (16)
    0x95, 0x01,        #   Report Count (1)
    0x81, 0x00,        #   Input (Data, Array, Absolute)
    0xC0               # End Collection (Consumer)
]

# Map characters to HID Usage Codes (simplified for a-z)
KEY_MAP = {
    'a': 0x04, 'b': 0x05, 'c': 0x06, 'd': 0x07, 'e': 0x08, 'f': 0x09,
    'g': 0x0A, 'h': 0x0B, 'i': 0x0C, 'j': 0x0D, 'k': 0x0E, 'l': 0x0F,
    'm': 0x10, 'n': 0x11, 'o': 0x12, 'p': 0x13, 'q': 0x14, 'r': 0x15,
    's': 0x16, 't': 0x17, 'u': 0x18, 'v': 0x19, 'w': 0x1A, 'x': 0x1B,
    'y': 0x1C, 'z': 0x1D, 'enter': 0x28, 'space': 0x2C,
}

class BTProfile(dbus.service.Object):
    def __init__(self, bus, path):
        super().__init__(bus, path)
        self.fd = -1
        self.is_connected = False
        self.intr_socket = None

    @dbus.service.method("org.bluez.Profile1", in_signature="", out_signature="")
    def Release(self):
        print("Release")
        sys.exit(0)

    @dbus.service.method("org.bluez.Profile1", in_signature="", out_signature="")
    def Cancel(self):
        print("Cancel")

    @dbus.service.method("org.bluez.Profile1", in_signature="oha{sv}", out_signature="")
    def NewConnection(self, path, fd, properties):
        print(f"DEBUG: NewConnection triggered from {path}")
        
        try:
            # 1. Get the file descriptor
            self.fd = fd.take()
            print(f"DEBUG: File descriptor {self.fd} taken successfully.")

            # 2. Setup the socket
            # Note: valid L2CAP sockets must be non-blocking or have timeouts handled carefully
            self.intr_socket = socket.fromfd(self.fd, socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET)
            self.intr_socket.setblocking(True) 
            
            self.is_connected = True
            print("Target Connected! Waiting 2 seconds for stability...")
            
            # 3. Schedule payload
            GLib.timeout_add(2000, self.execute_payload)
            
        except Exception as e:
            print(f"CRITICAL ERROR in NewConnection: {e}")
            # If we fail here, close the fd so the phone knows we failed
            if self.fd > -1:
                os.close(self.fd)

    @dbus.service.method("org.bluez.Profile1", in_signature="o", out_signature="")
    def RequestDisconnection(self, path):
        print(f"RequestDisconnection from {path}")
        self.is_connected = False
        if self.intr_socket:
            self.intr_socket.close()
            self.intr_socket = None

    def send_report(self, report_id, data):
        """Send a raw HID report."""
        if not self.is_connected or not self.intr_socket:
            return
        
        # Format: [0xA1 (DATA_HEADER), Report ID, ...Data...]
        # BlueZ raw socket usually expects the payload without the 0xA1 header 
        # if using the correct L2CAP channel, but for Profile API we often send pure HID data.
        # Note: 0xA1 is the HID Interrupt Data Header.
        payload = bytes([0xA1, report_id]) + bytes(data)
        try:
            self.intr_socket.sendall(payload)
        except OSError as e:
            print(f"Error sending report: {e}")

    def send_key(self, key_str):
        """Send a standard keyboard key press and release."""
        code = KEY_MAP.get(key_str)
        if not code:
            print(f"Unknown key: {key_str}")
            return
        
        # Press (Report ID 1, Modifiers 0, Res 0, Code, 0,0,0,0,0)
        self.send_report(1, [0, 0, code, 0, 0, 0, 0, 0])
        # Release
        self.send_report(1, [0, 0, 0, 0, 0, 0, 0, 0])
        time.sleep(0.05)

    def send_consumer(self, usage_value):
        """Send a Consumer Control command (e.g., Home, Search)."""
        # Usage is 16-bit little endian
        low = usage_value & 0xFF
        high = (usage_value >> 8) & 0xFF
        
        # Press (Report ID 2, Usage_Low, Usage_High)
        self.send_report(2, [low, high])
        # Release
        self.send_report(2, [0, 0])
        time.sleep(0.1)

    def execute_payload(self):
        print("Executing Payload...")
        
        # 1. AC Home (Usage 0x0223)
        print("Sending HOME...")
        self.send_consumer(0x0223)
        time.sleep(0.5)

        # 2. AC Search (Usage 0x0221)
        # Note: Some Android versions use AC Search (0x221), others respond to GUI (0xE3) + Enter.
        print("Sending SEARCH...")
        self.send_consumer(0x0221) 
        time.sleep(0.5) # Wait for search bar to appear

        # 3. Type 'chrome'
        print("Typing 'chrome'...")
        for char in "chrome":
            self.send_key(char)

        # 4. Enter
        print("Sending ENTER...")
        self.send_key("enter")
        
        print("Payload Complete.")
        return False # Don't repeat

def main():
    # DBus Loop Setup
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    
    # 1. Connect to BlueZ Profile Manager
    manager_obj = bus.get_object("org.bluez", "/org/bluez")
    manager = dbus.Interface(manager_obj, "org.bluez.ProfileManager1")

    # 2. Create our Profile Object
    profile = BTProfile(bus, PROFILE_DBUS_PATH)

    # 3. Register the Profile
    # Role 'server' usually means we are the device waiting for connection.
    opts = {
        "Name": "RPi5 Keyboard",
        "Role": "server",
        "ServiceRecord": SDP_RECORD_XML,
        "RequireAuthentication": False, # Try to avoid PIN if possible
        "RequireAuthorization": False,
    }
    
    print("Registering Bluetooth Profile...")
    manager.RegisterProfile(PROFILE_DBUS_PATH, "00001124-0000-1000-8000-00805f9b34fb", opts)
    
    print("Profile registered. Waiting for connection...")
    
    # 4. Run Main Loop
    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        print("Exit.")

if __name__ == "__main__":
    main()
