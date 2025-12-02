#!/bin/bash

# Stop execution if any command fails
set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}[*] Checking for root privileges...${NC}"
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}[!] Please run as root (sudo ./setup_blueducky.sh)${NC}"
  exit
fi

# 1. System Updates
echo -e "${BLUE}[*] Updating system packages...${NC}"
apt-get update
apt-get -y upgrade

# 2. Install Dependencies
echo -e "${BLUE}[*] Installing dependencies...${NC}"
apt install -y bluez-tools bluez-hcidump libbluetooth-dev \
               git gcc python3-pip python3-setuptools \
               python3-pydbus

# 3. Install PyBluez from source
echo -e "${BLUE}[*] Installing PyBluez...${NC}"
if [ -d "pybluez" ]; then rm -rf pybluez; fi
git clone https://github.com/pybluez/pybluez.git
cd pybluez
# We use try/catch logic here because newer Debian versions (Bookworm) 
# discourage direct setup.py usage, but we try it as per your request.
python3 setup.py install || echo -e "${RED}[!] Standard install failed, you might need to use pip with --break-system-packages manually later.${NC}"
cd ..
rm -rf pybluez

# 4. Build and Install bdaddr (With the Linker Fix)
echo -e "${BLUE}[*] Building bdaddr tool...${NC}"
if [ -d "bluez" ]; then rm -rf bluez; fi
git clone --depth=1 https://github.com/bluez/bluez.git
cd bluez

# FIX: Added -lbluetooth at the end to prevent "undefined reference" errors
gcc -o bdaddr tools/bdaddr.c src/oui.c -I . -lbluetooth

echo -e "${BLUE}[*] Installing bdaddr to /usr/local/bin/...${NC}"
cp bdaddr /usr/local/bin/
chmod +x /usr/local/bin/bdaddr
cd ..
rm -rf bluez

# 5. Apply "Service" Command Fix (For Arch/Minimal Debian)
# This fixes the "zsh: command not found: service" error
echo -e "${BLUE}[*] Checking for 'service' command wrapper...${NC}"
if ! command -v service &> /dev/null; then
    echo -e "${GREEN}[+] 'service' command not found. Creating compatibility wrapper...${NC}"
    echo -e '#!/bin/bash\nsystemctl "$2" "$1"' > /usr/local/bin/service
    chmod +x /usr/local/bin/service
    echo -e "${GREEN}[+] Wrapper created.${NC}"
else
    echo -e "${GREEN}[+] 'service' command already exists.${NC}"
fi

echo -e "${GREEN}[SUCCESS] Setup complete! You can now run your bluetoothAttack.py script.${NC}"
