# Reverse-Engineering-Project

**A streamlined, single-file implementation of CVE-2023-45866.**

This project is a modified version of the original BlueDucky, designed for stability on Raspberry Pi 5 and ease of use.

## Vulnerability
**CVE-2023-45866** - Unauthenticated Peering Leading to Code Execution.
This tool exploits a vulnerability in Bluetooth stacks to inject keystrokes into a target device without a visual pairing prompt.


## Installation

We have provided an automated setup script that handles dependencies, compiles the necessary tools, and fixes the `service` command on Arch/Minimal systems.

### 1. Download the Project
```bash
# Clone this repository or copy the files to your directory
git clone https://github.com/WokyDoky/Reverse-Engineering-Project
cd Reverse-Engineering-Project
```

### 2. Run the Setup Script
```bash
chmod +x setup_blueducky.sh
sudo ./setup_blueducky.sh
```
### 3. Run the attack
```bash
sudo python3 bluetoothAttack.py
```
## Operation
1. The script will ask if you want to target the default address (18:68:6A:FA:10:43).
    - Type y to attack immediately.
    - Type n to scan for other devices.

2. Once connected, the script waits 5 seconds for the connection to stabilize.

3. It wakes the device and executes the payload:
    - Action: Arrow Down
    - Action: Arrow Right (4 times)
4. The script terminates automatically after execution.

## Credits
- Based on the original [BlueDucky](https://github.com/pentestfunctions/BlueDucky) by pentestfunctions.
- Original CVE discovery by [marcnewlin](https://github.com/marcnewlin).
