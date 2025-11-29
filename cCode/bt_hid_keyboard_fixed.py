#!/usr/bin/env python3
"""
bt_hid_keyboard_fixed.py
Improved Bluetooth HID Keyboard for Raspberry Pi 5
Handles both Control and Interrupt channels properly
"""

import os
import sys
import time
import socket
import threading
import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib

# Configuration
DEVICE_NAME = "RPi5-Keyboard"
P_CTRL = 17  # HID Control PSM
P_INTR = 19  # HID Interrupt PSM

# HID Report Descriptor (Boot Keyboard)
HID_REPORT_DESC = bytes([
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
    0x81, 0x02,  #   Input (Data, Variable, Absolute)
    0x95, 0x01,  #   Report Count (1)
    0x75, 0x08,  #   Report Size (8)
    0x81, 0x01,  #   Input (Constant)
    0x95, 0x06,  #   Report Count (6)
    0x75, 0x08,  #   Report Size (8)
    0x15, 0x00,  #   Logical Minimum (0)
    0x25, 0x65,  #   Logical Maximum (101)
    0x05, 0x07,  #   Usage Page (Key Codes)
    0x19, 0x00,  #   Usage Minimum (0)
    0x29, 0x65,  #   Usage Maximum (101)
    0x81, 0x00,  #   Input (Data, Array)
    0xC0         # End Collection
])

# SDP Record
SDP_RECORD = """<?xml version="1.0" encoding="UTF-8" ?>
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
  <attribute id="0x0006">
    <sequence>
      <uint16 value="0x656e"/>
      <uint16 value="0x006a"/>
      <uint16 value="0x0100"/>
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
    <text value="Raspberry Pi Keyboard"/>
  </attribute>
  <attribute id="0x0101">
    <text value="USB > BT Keyboard"/>
  </attribute>
  <attribute id="0x0102">
    <text value="Raspberry Pi"/>
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
  <attribute id="0x0203">
    <uint8 value="0x00"/>
  </attribute>
  <attribute id="0x0204">
    <uint8 value="0x01"/>
  </attribute>
  <attribute id="0x0205">
    <uint8 value="0x01"/>
  </attribute>
  <attribute id="0x0206">
    <sequence>
      <sequence>
        <uint8 value="0x22"/>
        <text encoding="hex" value="{descriptor}"/>
      </sequence>
    </sequence>
  </attribute>
  <attribute id="0x0207">
    <sequence>
      <sequence>
        <uint16 value="0x0409"/>
        <uint16 value="0x0100"/>
      </sequence>
    </sequence>
  </attribute>
  <attribute id="0x020b">
    <uint16 value="0x0100"/>
  </attribute>
  <attribute id="0x020c">
    <uint16 value="0x0c80"/>
  </attribute>
  <attribute id="0x020d">
    <uint8 value="0x01"/>
  </attribute>
  <attribute id="0x020e">
    <uint8 value="0x01"/>
  </attribute>
  <attribute id="0x020f">
    <uint16 value="0x0640"/>
  </attribute>
  <attribute id="0x0210">
    <uint16 value="0x0320"/>
  </attribute>
</record>
""".format(descriptor=HID_REPORT_DESC.hex())

# HID Keycodes
KEYCODE_MAP = {
    'a': 0x04, 'b': 0x05, 'c': 0x06, 'd': 0x07, 'e': 0x08,
    'f': 0x09, 'g': 0x0A, 'h': 0x0B, 'i': 0x0C, 'j': 0x0D,
    'k': 0x0E, 'l': 0x0F, 'm': 0x10, 'n': 0x11, 'o': 0x12,
    'p': 0x13, 'q': 0x14, 'r': 0x15, 's': 0x16, 't': 0x17,
    'u': 0x18, 'v': 0x19, 'w': 0x1A, 'x': 0x1B, 'y': 0x1C,
    'z': 0x1D, '1': 0x1E, '2': 0x1F, '3': 0x20, '4': 0x21,
    '5': 0x22, '6': 0x23, '7': 0x24, '8': 0x25, '9': 0x26,
    '0': 0x27, '\n': 0x28, ' ': 0x2C
}

KEY_HOME = 0x4A
KEY_SEARCH = 0x221  # Not standard HID - won't work on most devices
MOD_GUI = 0x08  # Left GUI/Windows/Super key

dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

class BTKbDevice:
    """Bluetooth HID Keyboard Device"""
    
    def __init__(self):
        self.scontrol = None
        self.sinterrupt = None
        self.connected = False
        self.lock = threading.Lock()
        
    def listen(self):
        """Create listening sockets for HID control and interrupt channels"""
        print("[*] Setting up HID sockets...")
        
        # Control channel (PSM 17)
        self.scontrol = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP)
        self.scontrol.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.scontrol.bind(("", P_CTRL))
        self.scontrol.listen(1)
        
        # Interrupt channel (PSM 19)
        self.sinterrupt = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP)
        self.sinterrupt.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sinterrupt.bind(("", P_INTR))
        self.sinterrupt.listen(1)
        
        print(f"[*] Listening on PSM {P_CTRL} (control) and PSM {P_INTR} (interrupt)")
        
        # Start accept threads
        threading.Thread(target=self._accept_control, daemon=True).start()
        threading.Thread(target=self._accept_interrupt, daemon=True).start()
        
    def _accept_control(self):
        """Accept control channel connections"""
        while True:
            try:
                print("[*] Waiting for control channel connection...")
                client, addr = self.scontrol.accept()
                print(f"[+] Control channel connected from {addr}")
                with self.lock:
                    self.ccontrol = client
            except Exception as e:
                print(f"[!] Control accept error: {e}")
                time.sleep(1)
                
    def _accept_interrupt(self):
        """Accept interrupt channel connections"""
        while True:
            try:
                print("[*] Waiting for interrupt channel connection...")
                client, addr = self.sinterrupt.accept()
                print(f"[+] Interrupt channel connected from {addr}")
                with self.lock:
                    self.cinterrupt = client
                    # Both channels connected - trigger payload
                    if hasattr(self, 'ccontrol') and hasattr(self, 'cinterrupt'):
                        self.connected = True
                        threading.Thread(target=self._run_payload, daemon=True).start()
            except Exception as e:
                print(f"[!] Interrupt accept error: {e}")
                time.sleep(1)
                
    def _run_payload(self):
        """Execute the attack payload"""
        print("[*] Both channels connected, waiting 2 seconds...")
        time.sleep(2)
        
        try:
            print("[*] Executing payload...")
            
            # Try to wake device with Space key
            print("[*] Sending space key to wake device...")
            self.send_key(0x2C)  # Space
            time.sleep(0.5)
            
            # Swipe up gesture simulation (this won't work via keyboard)
            # Instead, try opening app drawer with known key combos
            
            # On some Android devices, search can be triggered
            # Let's try: Long press on space or use GUI key combinations
            
            # Method 1: Try GUI+S (might open search on some launchers)
            print("[*] Attempting to open search...")
            self.send_key(0x16, modifier=MOD_GUI)  # GUI+S
            time.sleep(1)
            
            # Method 2: Type chrome directly (if search opened)
            print("[*] Typing 'chrome'...")
            self.send_string("chrome")
            time.sleep(0.5)
            
            # Send Enter
            print("[*] Sending Enter...")
            self.send_key(0x28)  # Enter
            time.sleep(0.5)
            
            print("[+] Payload complete!")
            
        except Exception as e:
            print(f"[!] Payload error: {e}")
            
    def send_key(self, keycode, modifier=0):
        """Send a single keystroke (press + release)"""
        # Press
        report = bytes([0xA1, 0x01, modifier, 0x00, keycode, 0x00, 0x00, 0x00, 0x00, 0x00])
        with self.lock:
            if hasattr(self, 'cinterrupt'):
                self.cinterrupt.send(report)
        time.sleep(0.05)
        
        # Release
        report = bytes([0xA1, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        with self.lock:
            if hasattr(self, 'cinterrupt'):
                self.cinterrupt.send(report)
        time.sleep(0.05)
        
    def send_string(self, text):
        """Type a string of characters"""
        for char in text.lower():
            if char in KEYCODE_MAP:
                self.send_key(KEYCODE_MAP[char])
            else:
                print(f"[!] Unsupported character: {char}")

class HIDProfile(dbus.service.Object):
    """D-Bus Profile for HID"""
    
    def __init__(self, bus, path):
        super().__init__(bus, path)
        
    @dbus.service.method("org.bluez.Profile1", in_signature="", out_signature="")
    def Release(self):
        print("[D-Bus] Profile released")
        
    @dbus.service.method("org.bluez.Profile1", in_signature="oha{sv}", out_signature="")
    def NewConnection(self, path, fd, properties):
        print(f"[D-Bus] NewConnection called for {path}")
        # We handle connections via raw sockets, so we can ignore this
        # or close the fd
        try:
            fd_int = fd.take() if hasattr(fd, 'take') else int(fd)
            os.close(fd_int)
        except:
            pass
            
    @dbus.service.method("org.bluez.Profile1", in_signature="o", out_signature="")
    def RequestDisconnection(self, path):
        print(f"[D-Bus] Disconnection requested for {path}")

def register_hid_profile():
    """Register the HID profile with BlueZ"""
    bus = dbus.SystemBus()
    
    # Set adapter properties
    try:
        manager = dbus.Interface(bus.get_object("org.bluez", "/"), "org.freedesktop.DBus.ObjectManager")
        objects = manager.GetManagedObjects()
        
        adapter_path = None
        for path, interfaces in objects.items():
            if "org.bluez.Adapter1" in interfaces:
                adapter_path = path
                break
                
        if adapter_path:
            adapter = dbus.Interface(bus.get_object("org.bluez", adapter_path), "org.freedesktop.DBus.Properties")
            adapter.Set("org.bluez.Adapter1", "Alias", DEVICE_NAME)
            adapter.Set("org.bluez.Adapter1", "Discoverable", True)
            adapter.Set("org.bluez.Adapter1", "Pairable", True)
            print(f"[*] Adapter configured: {DEVICE_NAME}")
    except Exception as e:
        print(f"[!] Adapter config error: {e}")
        
    # Register profile
    try:
        service_path = "/org/bluez/hid"
        profile = HIDProfile(bus, service_path)
        
        manager = dbus.Interface(bus.get_object("org.bluez", "/org/bluez"), "org.bluez.ProfileManager1")
        
        opts = {
            "Role": "server",
            "RequireAuthentication": False,
            "RequireAuthorization": False,
            "ServiceRecord": SDP_RECORD,
        }
        
        manager.RegisterProfile(service_path, "00001124-0000-1000-8000-00805f9b34fb", opts)
        print("[*] HID Profile registered with BlueZ")
        return profile
    except Exception as e:
        print(f"[!] Profile registration error: {e}")
        sys.exit(1)

def main():
    if os.geteuid() != 0:
        print("[!] This script must be run as root")
        sys.exit(1)
        
    print("[*] Starting Bluetooth HID Keyboard")
    print("[*] Device name:", DEVICE_NAME)
    
    # Register D-Bus profile
    profile = register_hid_profile()
    
    # Create HID device and start listening
    device = BTKbDevice()
    device.listen()
    
    print("\n[*] Ready! Pair from your Android device now.")
    print("[*] Go to: Settings > Bluetooth > Search for devices")
    print("[*] Select 'RPi5-Keyboard' and pair")
    print("[*] Press Ctrl+C to exit\n")
    
    # Run GLib main loop
    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        print("\n[*] Exiting...")
        loop.quit()

if __name__ == "__main__":
    main()
