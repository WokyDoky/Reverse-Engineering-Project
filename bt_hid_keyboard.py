
#!/usr/bin/env python3
"""
bt_hid_keyboard.py
Present Raspberry Pi as a Bluetooth Classic HID keyboard using BlueZ D-Bus Profile API.

Requires: python3-dbus, python3-gi
Run as root: sudo python3 bt_hid_keyboard.py
"""

import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib
import array
import os
import sys
import time
import threading
import struct
import fcntl
import socket

# ---------- Configuration ----------
DEVICE_NAME = "RPI-HID-Keyboard"
SERVICE_RECORD_PATH = "/org/bluez/example/hid_profile"
# Standard keyboard report descriptor (USB HID Keyboard, 8-byte reports: modifiers, reserved, 6 keycodes)
# This is a minimal descriptor for a boot keyboard (works on many hosts)
HID_REPORT_DESCRIPTOR = bytes([
    0x05, 0x01,        # Usage Page (Generic Desktop)
    0x09, 0x06,        # Usage (Keyboard)
    0xA1, 0x01,        # Collection (Application)
    0x05, 0x07,        #   Usage Page (Key Codes)
    0x19, 0xE0,        #   Usage Minimum (224) - Left Control
    0x29, 0xE7,        #   Usage Maximum (231) - Right GUI
    0x15, 0x00,        #   Logical Minimum (0)
    0x25, 0x01,        #   Logical Maximum (1)
    0x75, 0x01,        #   Report Size (1)
    0x95, 0x08,        #   Report Count (8) - 8 modifier bits
    0x81, 0x02,        #   Input (Data, Variable, Absolute) ; Modifier byte
    0x95, 0x01,        #   Report Count (1)
    0x75, 0x08,        #   Report Size (8)
    0x81, 0x01,        #   Input (Constant) ; Reserved byte
    0x95, 0x06,        #   Report Count (6)
    0x75, 0x08,        #   Report Size (8)
    0x15, 0x00,        #   Logical Minimum (0)
    0x25, 0x65,        #   Logical Maximum (101)
    0x05, 0x07,        #   Usage Page (Keyboard)
    0x19, 0x00,        #   Usage Minimum (0)
    0x29, 0x65,        #   Usage Maximum (101)
    0x81, 0x00,        #   Input (Data, Array) ; Key arrays (6 bytes)
    0xC0               # End Collection
])

# Standard HID SDP XML record for a keyboard (Bluetooth Classic HID)
HID_SDP_RECORD = """<?xml version="1.0" encoding="UTF-8" ?>
<record>
  <attribute id="0x0001">
    <sequence>
      <uuid value="0x1124"/> <!-- HID service -->
    </sequence>
  </attribute>
  <attribute id="0x0004">
    <sequence>
      <sequence>
        <uuid value="0x0100"/> <!-- L2CAP -->
        <uint8 value="0x11"/>
      </sequence>
      <sequence>
        <uuid value="0x0011"/> <!-- HID -->
        <uint8 value="0x13"/>
      </sequence>
    </sequence>
  </attribute>
  <attribute id="0x0005">
    <sequence>
      <uuid value="0x1002"/>
    </sequence>
  </attribute>
  <attribute id="0x0009">
    <uint16 value="0x0100"/>
  </attribute>
  <attribute id="0x0100">
    <text value="{name}"/>
  </attribute>
  <attribute id="0x0200">
    <uint8 value="0x01"/>
  </attribute>
  <attribute id="0x0201">
    <uint8 value="0x01"/>
  </attribute>
  <attribute id="0x0202">
    <uint16 value="0x0000"/>
  </attribute>
  <attribute id="0x0203">
    <uint16 value="{vendor}"/>
  </attribute>
  <attribute id="0x0204">
    <uint16 value="{product}"/>
  </attribute>
  <attribute id="0x0205">
    <uint16 value="0x0110"/>
  </attribute>
  <attribute id="0x0206">
    <uint8 value="0x22"/>
  </attribute>
  <attribute id="0x0207">
    <uint8 value="0x01"/>
  </attribute>
  <attribute id="0x0208">
    <sequence>
      <sequence>
        <uint8 value="0x22"/>
        <text encoding="hex" value="{report_desc_hex}"/>
      </sequence>
    </sequence>
  </attribute>
</record>
""".format(name=DEVICE_NAME,
           vendor=0xFFFF,    # vendor/product id placeholders
           product=0x0001,
           report_desc_hex=HID_REPORT_DESCRIPTOR.hex())

# ---------- USB HID usage tables (subset) ----------
# HID usage codes for letters and Enter are standard (USB HID Usage IDs)
# We'll map ASCII letters to HID keycodes (lowercase only). This map is minimal and
# covers the letters we need ("chrome") and Enter.
CHAR_TO_KEYCODE = {
    'a': 0x04, 'b': 0x05, 'c': 0x06, 'd': 0x07, 'e': 0x08, 'f': 0x09,
    'g': 0x0A, 'h': 0x0B, 'i': 0x0C, 'j': 0x0D, 'k': 0x0E, 'l': 0x0F,
    'm': 0x10, 'n': 0x11, 'o': 0x12, 'p': 0x13, 'q': 0x14, 'r': 0x15,
    's': 0x16, 't': 0x17, 'u': 0x18, 'v': 0x19, 'w': 0x1A, 'x': 0x1B,
    'y': 0x1C, 'z': 0x1D,
    '1': 0x1E, '2': 0x1F, '3': 0x20, '4': 0x21, '5': 0x22,
    '6': 0x23, '7': 0x24, '8': 0x25, '9': 0x26, '0': 0x27,
    '\n': 0x28  # Enter
}

MOD_SHIFT = 0x02
MOD_LEFT_GUI = 0x08

# ---------- Helper to build HID reports ----------
def make_keyboard_report(modifier, keycodes):
    """
    8-byte report: [modifier][reserved][k1][k2][k3][k4][k5][k6]
    keycodes length <= 6
    """
    rep = [0] * 8
    rep[0] = modifier & 0xFF
    rep[1] = 0x00  # reserved
    for i, k in enumerate(keycodes[:6]):
        rep[2 + i] = k
    return bytes(rep)

# ---------- D-Bus Profile Implementation ----------
dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

BUS = dbus.SystemBus()

class HIDProfile(dbus.service.Object):
    """
    Implements org.bluez.Profile1 for a HID device.
    BlueZ will call NewConnection() and pass us an fd for the connected L2CAP channel.
    """
    def __init__(self, path):
        self.path = path
        bus_name = dbus.service.BusName("org.bluez", bus=BUS)
        super().__init__(bus_name, path)
        self.conn_sock = None
        self.conn_lock = threading.Lock()
        self.connected = False

    @dbus.service.method("org.bluez.Profile1", in_signature="", out_signature="")
    def Release(self):
        print("[Profile] Released by BlueZ")
        with self.conn_lock:
            if self.conn_sock:
                try:
                    self.conn_sock.close()
                except:
                    pass
                self.conn_sock = None
                self.connected = False

    @dbus.service.method("org.bluez.Profile1",
                         in_signature="oha{sv}", out_signature="")
    def NewConnection(self, device, fd, fd_properties):
        # fd is a file descriptor (unix file descriptor)
        print(f"[Profile] NewConnection from {device}")
        # fd comes as a dbus.UnixFd; convert and wrap into python socket
        fd = fd.take() if hasattr(fd, "take") else int(fd)
        # Create socket from fd (it is a stream socket)
        conn_sock = socket.fromfd(fd, socket.AF_UNIX, socket.SOCK_STREAM)
        # We need to duplicate FD because closing will close underlying fd; create a duplicate
        # (fromfd already duplicates on many systems) — but to be safe, duplicate:
        dup_fd = os.dup(conn_sock.fileno())
        real_sock = socket.socket(family=socket.AF_UNIX, type=socket.SOCK_STREAM, fileno=dup_fd)

        # put socket in blocking mode
        real_sock.setblocking(True)

        with self.conn_lock:
            if self.conn_sock:
                try:
                    self.conn_sock.close()
                except:
                    pass
            self.conn_sock = real_sock
            self.connected = True

        # spawn a thread to handle payload after waiting
        t = threading.Thread(target=self._on_connected_and_send_payload, args=(device,))
        t.daemon = True
        t.start()

    @dbus.service.method("org.bluez.Profile1", in_signature="o", out_signature="")
    def RequestDisconnection(self, device):
        print(f"[Profile] RequestDisconnection from BlueZ for {device}")
        with self.conn_lock:
            if self.conn_sock:
                try:
                    self.conn_sock.close()
                except:
                    pass
                self.conn_sock = None
                self.connected = False

    def _send_raw(self, data: bytes):
        """Write raw bytes to the L2CAP socket. Thread-safe."""
        with self.conn_lock:
            if not self.conn_sock:
                raise IOError("No connection socket")
            try:
                totalsent = 0
                while totalsent < len(data):
                    sent = self.conn_sock.send(data[totalsent:])
                    if sent <= 0:
                        raise IOError("Socket send returned 0")
                    totalsent += sent
                return totalsent
            except Exception as e:
                print("[Profile] Error sending data:", e)
                # close socket
                try:
                    self.conn_sock.close()
                except:
                    pass
                self.conn_sock = None
                self.connected = False
                raise

    def _on_connected_and_send_payload(self, device):
        print("[Profile] Connected; waiting 2 seconds for stability")
        time.sleep(2.0)

        # Best-effort: attempt a Home wake. Many Android devices don't map a standard HID key
        # to Home. We try Left GUI (modifier) + 'h' (this is *not* guaranteed).
        try:
            print("[Payload] Attempting best-effort Home/Wake (may be ignored by Android)")
            # Try left GUI down + release (best-effort)
            r = make_keyboard_report(MOD_LEFT_GUI, [])
            self._send_raw(r)
            time.sleep(0.05)
            r = make_keyboard_report(0, [])
            self._send_raw(r)
        except Exception as e:
            print("[Payload] Home attempt failed:", e)

        # Now type "chrome" and Enter
        try:
            print("[Payload] Typing 'chrome' + Enter")
            self.send_text("chrome")
            time.sleep(0.05)
            self.send_keystroke(CHAR_TO_KEYCODE.get('\n'))  # Enter
            print("[Payload] Sent Enter")
        except Exception as e:
            print("[Payload] Error during payload:", e)

    # Public API: send a single HID key (press+release)
    def send_keystroke(self, keycode, modifier=0):
        if keycode is None:
            return
        # Press
        rpt = make_keyboard_report(modifier, [keycode])
        self._send_raw(rpt)
        time.sleep(0.06)
        # Release
        rpt = make_keyboard_report(0, [])
        self._send_raw(rpt)
        time.sleep(0.02)

    def send_text(self, text):
        """Type ascii lowercase letters (no special char handling implemented)."""
        for ch in text:
            if ch in CHAR_TO_KEYCODE:
                kc = CHAR_TO_KEYCODE[ch]
                self.send_keystroke(kc)
            else:
                # If uppercase letter, send Shift modifier + letter
                if ch.isupper():
                    low = ch.lower()
                    if low in CHAR_TO_KEYCODE:
                        self.send_keystroke(CHAR_TO_KEYCODE[low], MOD_SHIFT)
                else:
                    print("[send_text] Character not supported:", repr(ch))

# ---------- Register Profile with BlueZ ----------
def register_profile(profile_obj):
    """
    Register Profile1 object with BlueZ ProfileManager1.
    """
    manager = dbus.Interface(BUS.get_object("org.bluez", "/org/bluez"),
                             "org.bluez.ProfileManager1")

    opts = {
        # ServiceRecord is SDP XML for the HID device
        "ServiceRecord": dbus.String(HID_SDP_RECORD),
        "Role": dbus.String("server"),
        # Bluetooth class of device: 0x0504 examples: peripheral, keyboard
        "RequireAuthentication": dbus.Boolean(True),
        "RequireAuthorization": dbus.Boolean(False),
    }

    print("[Main] Registering HID Profile with BlueZ")
    manager.RegisterProfile(SERVICE_RECORD_PATH, "00001124-0000-1000-8000-00805f9b34fb", opts)
    print("[Main] Profile registered.")

def main():
    # Create profile object
    profile = HIDProfile(SERVICE_RECORD_PATH)

    # Create an adapter alias name (optional): we will set the name shown to remote devices
    try:
        # Set Bluetooth system adapter name to the DEVICE_NAME for visibility
        adapter_path = None
        obj_manager = dbus.Interface(BUS.get_object("org.bluez", "/"), "org.freedesktop.DBus.ObjectManager")
        objects = obj_manager.GetManagedObjects()
        for path, ifaces in objects.items():
            if "org.bluez.Adapter1" in ifaces:
                adapter_path = path
                break
        if adapter_path:
            adapter = BUS.get_object("org.bluez", adapter_path)
            props = dbus.Interface(adapter, "org.freedesktop.DBus.Properties")
            props.Set("org.bluez.Adapter1", "Alias", dbus.String(DEVICE_NAME))
            print(f"[Main] Adapter alias set to {DEVICE_NAME}")
    except Exception as e:
        print("[Main] Could not set adapter alias:", e)

    # Register profile with BlueZ
    try:
        register_profile(profile)
    except Exception as e:
        print("[Main] Failed to register profile:", e)
        sys.exit(1)

    print("[Main] Waiting for incoming connections. Pair from the Android device now.")
    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        print("[Main] Interrupted by user, unregistering profile.")
        try:
            manager = dbus.Interface(BUS.get_object("org.bluez", "/org/bluez"), "org.bluez.ProfileManager1")
            manager.UnregisterProfile(SERVICE_RECORD_PATH)
        except Exception:
            pass
        loop.quit()

if __name__ == "__main__":
    main()
