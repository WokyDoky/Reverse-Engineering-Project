#!/usr/bin/env python3
"""
bt_hid_diagnostic.py
Diagnostic tool to check Bluetooth HID setup and troubleshoot issues
"""

import os
import sys
import subprocess
import socket

def print_header(text):
    print("\n" + "="*60)
    print(text)
    print("="*60)

def run_command(cmd, description):
    """Run a shell command and display output"""
    print(f"\n[*] {description}")
    print(f"    Command: {cmd}")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(f"    STDERR: {result.stderr}")
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print("    [!] Command timed out")
        return False
    except Exception as e:
        print(f"    [!] Error: {e}")
        return False

def check_root():
    """Check if running as root"""
    print_header("1. ROOT PRIVILEGES CHECK")
    if os.geteuid() == 0:
        print("[✓] Running as root")
        return True
    else:
        print("[✗] NOT running as root")
        print("    Please run with: sudo python3 bt_hid_diagnostic.py")
        return False

def check_bluetooth_service():
    """Check if Bluetooth service is running"""
    print_header("2. BLUETOOTH SERVICE STATUS")
    return run_command("systemctl status bluetooth | head -20", "Checking Bluetooth service")

def check_bluetooth_config():
    """Check Bluetooth configuration"""
    print_header("3. BLUETOOTH CONFIGURATION")
    
    print("\n[*] Checking /etc/bluetooth/main.conf:")
    try:
        with open('/etc/bluetooth/main.conf', 'r') as f:
            in_general = False
            for line in f:
                line = line.strip()
                if line == '[General]':
                    in_general = True
                    print(f"    {line}")
                elif in_general:
                    if line.startswith('['):
                        break
                    if line and not line.startswith('#'):
                        print(f"    {line}")
                        
                        # Check specific settings
                        if 'DisablePlugins' in line:
                            if 'input' in line:
                                print("        [✓] Input plugin disabled")
                            else:
                                print("        [!] Input plugin may not be disabled")
    except Exception as e:
        print(f"    [!] Error reading config: {e}")

def check_python_dependencies():
    """Check if required Python modules are installed"""
    print_header("4. PYTHON DEPENDENCIES")
    
    modules = {
        'dbus': 'python3-dbus',
        'gi': 'python3-gi',
        'bluetooth': 'python3-bluez (PyBluez)'
    }
    
    all_ok = True
    for module, package in modules.items():
        try:
            __import__(module)
            print(f"[✓] {module} ({package})")
        except ImportError:
            print(f"[✗] {module} NOT FOUND - Install: {package}")
            all_ok = False
            
    return all_ok

def check_adapter_info():
    """Check Bluetooth adapter information"""
    print_header("5. BLUETOOTH ADAPTER INFO")
    
    run_command("hciconfig -a", "Adapter configuration (hciconfig)")
    run_command("bluetoothctl show", "Adapter details (bluetoothctl)")

def check_hid_sockets():
    """Check if HID PSM ports are available"""
    print_header("6. HID SOCKET AVAILABILITY")
    
    print("\n[*] Testing L2CAP socket creation:")
    psms = [17, 19]  # Control and Interrupt
    
    for psm in psms:
        try:
            sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP)
            sock.bind(("", psm))
            sock.close()
            print(f"[✓] PSM {psm} is available")
        except PermissionError:
            print(f"[✗] PSM {psm} - Permission denied (need root)")
        except OSError as e:
            print(f"[✗] PSM {psm} - {e}")
        except Exception as e:
            print(f"[✗] PSM {psm} - Unexpected error: {e}")

def check_dbus_bluez():
    """Check BlueZ D-Bus interface"""
    print_header("7. BLUEZ D-BUS INTERFACE")
    
    try:
        import dbus
        bus = dbus.SystemBus()
        
        print("[*] Checking BlueZ object manager:")
        obj_manager = dbus.Interface(
            bus.get_object("org.bluez", "/"),
            "org.freedesktop.DBus.ObjectManager"
        )
        objects = obj_manager.GetManagedObjects()
        
        adapters = []
        for path, interfaces in objects.items():
            if "org.bluez.Adapter1" in interfaces:
                adapters.append(path)
                print(f"[✓] Found adapter: {path}")
                
                # Get adapter properties
                adapter = dbus.Interface(
                    bus.get_object("org.bluez", path),
                    "org.freedesktop.DBus.Properties"
                )
                alias = adapter.Get("org.bluez.Adapter1", "Alias")
                address = adapter.Get("org.bluez.Adapter1", "Address")
                powered = adapter.Get("org.bluez.Adapter1", "Powered")
                discoverable = adapter.Get("org.bluez.Adapter1", "Discoverable")
                
                print(f"    Alias: {alias}")
                print(f"    Address: {address}")
                print(f"    Powered: {powered}")
                print(f"    Discoverable: {discoverable}")
                
        if not adapters:
            print("[✗] No Bluetooth adapters found!")
            return False
            
        return True
        
    except ImportError:
        print("[✗] python3-dbus not installed")
        return False
    except Exception as e:
        print(f"[✗] Error: {e}")
        return False

def check_sdp_tools():
    """Check SDP tools availability"""
    print_header("8. SDP TOOLS")
    
    tools = ['sdptool', 'btmon']
    for tool in tools:
        result = subprocess.run(['which', tool], capture_output=True)
        if result.returncode == 0:
            print(f"[✓] {tool} is available: {result.stdout.decode().strip()}")
        else:
            print(f"[✗] {tool} not found")
            if tool == 'sdptool':
                print("    Install: sudo apt-get install bluez-deprecated")
            else:
                print("    Install: sudo apt-get install bluez")

def test_profile_registration():
    """Test D-Bus profile registration"""
    print_header("9. TEST PROFILE REGISTRATION")
    
    try:
        import dbus
        import dbus.service
        import dbus.mainloop.glib
        from gi.repository import GLib
        
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        bus = dbus.SystemBus()
        
        print("[*] Creating test profile...")
        
        class TestProfile(dbus.service.Object):
            def __init__(self, bus, path):
                super().__init__(bus, path)
                
            @dbus.service.method("org.bluez.Profile1", in_signature="", out_signature="")
            def Release(self):
                pass
                
            @dbus.service.method("org.bluez.Profile1", in_signature="oha{sv}", out_signature="")
            def NewConnection(self, path, fd, properties):
                pass
                
            @dbus.service.method("org.bluez.Profile1", in_signature="o", out_signature="")
            def RequestDisconnection(self, path):
                pass
        
        test_path = "/org/bluez/test_diagnostic"
        profile = TestProfile(bus, test_path)
        
        manager = dbus.Interface(
            bus.get_object("org.bluez", "/org/bluez"),
            "org.bluez.ProfileManager1"
        )
        
        # Minimal options
        opts = {
            "Role": "server",
            "RequireAuthentication": False,
            "RequireAuthorization": False,
        }
        
        print("[*] Registering test profile...")
        manager.RegisterProfile(test_path, "00001124-0000-1000-8000-00805f9b34fb", opts)
        print("[✓] Profile registration successful!")
        
        print("[*] Unregistering test profile...")
        manager.UnregisterProfile(test_path)
        print("[✓] Profile unregistration successful!")
        
        return True
        
    except ImportError as e:
        print(f"[✗] Missing dependency: {e}")
        return False
    except dbus.exceptions.DBusException as e:
        print(f"[✗] D-Bus error: {e}")
        return False
    except Exception as e:
        print(f"[✗] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

def generate_recommendations():
    """Generate recommendations based on checks"""
    print_header("10. RECOMMENDATIONS")
    
    print("""
Based on the diagnostic results above, here are some recommendations:

1. If Bluetooth service is not running:
   sudo systemctl start bluetooth
   sudo systemctl enable bluetooth

2. If input plugin is not disabled:
   Edit /etc/bluetooth/main.conf:
   [General]
   DisablePlugins = input
   
   Then restart: sudo systemctl restart bluetooth

3. If Python dependencies are missing:
   sudo apt-get update
   sudo apt-get install python3-dbus python3-gi python3-bluez

4. If PSM ports are not available:
   - Make sure you're running as root
   - Check if another HID service is using them:
     sudo netstat -l | grep bluetooth

5. If profile registration fails:
   - Check BlueZ version: bluetoothctl --version
   - Ensure BlueZ is recent (5.50+)
   - Check journalctl: sudo journalctl -u bluetooth -f

6. For monitoring connections:
   sudo btmon
   
7. To verify HID service registration:
   sdptool browse local

8. Common issues:
   - Device must be unpaired before retrying
   - Restart Bluetooth service after config changes
   - Some Android versions require authentication
   - Connection may drop if channels don't establish quickly
    """)

def main():
    print("""
╔══════════════════════════════════════════════════════════╗
║   Bluetooth HID Keyboard - Diagnostic Tool              ║
║   For Raspberry Pi 5 / BlueZ 5.x                         ║
╚══════════════════════════════════════════════════════════╝
    """)
    
    checks = [
        ("Root check", check_root),
        ("Bluetooth service", check_bluetooth_service),
        ("Bluetooth config", check_bluetooth_config),
        ("Python dependencies", check_python_dependencies),
        ("Adapter info", check_adapter_info),
        ("HID socket availability", check_hid_sockets),
        ("BlueZ D-Bus interface", check_dbus_bluez),
        ("SDP tools", check_sdp_tools),
        ("Profile registration", test_profile_registration),
    ]
    
    results = {}
    for name, check_func in checks:
        try:
            results[name] = check_func()
        except Exception as e:
            print(f"\n[!] Error during {name}: {e}")
            results[name] = False
    
    # Generate recommendations
    generate_recommendations()
    
    # Summary
    print_header("SUMMARY")
    for name, result in results.items():
        status = "[✓]" if result else "[✗]"
        print(f"{status} {name}")
    
    print("\n[*] Diagnostic complete!")
    print("[*] Review the results above and follow recommendations.")

if __name__ == "__main__":
    main()
