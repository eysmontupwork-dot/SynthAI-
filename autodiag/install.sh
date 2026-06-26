#!/bin/bash
# SynthAI — Automated installation v2.1

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

clear
echo -e "${BLUE}"
echo "  ███████╗██╗   ██╗███╗   ██╗████████╗██╗  ██╗ █████╗ ██╗"
echo "  ██╔════╝╚██╗ ██╔╝████╗  ██║╚══██╔══╝██║  ██║██╔══██╗██║"
echo "  ███████╗ ╚████╔╝ ██╔██╗ ██║   ██║   ███████║███████║██║"
echo "  ╚════██║  ╚██╔╝  ██║╚██╗██║   ██║   ██╔══██║██╔══██║██║"
echo "  ███████║   ██║   ██║ ╚████║   ██║   ██║  ██║██║  ██║██║"
echo "  ╚══════╝   ╚═╝   ╚═╝  ╚═══╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝"
echo -e "${NC}"
echo -e "${GREEN}  AI Diagnostic Stand — Installation v2.1${NC}"
echo "  ================================================"
echo ""

# Check Ubuntu
echo -e "${CYAN}Checking system...${NC}"
if ! grep -q "Ubuntu" /etc/os-release; then
    echo -e "${RED}Error: Only Ubuntu is supported!${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Ubuntu detected${NC}"

# Check internet connection
if ! ping -c 1 google.com &>/dev/null; then
    echo -e "${RED}Error: No internet connection!${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Internet available${NC}"

# FIXED: Python 3.11 or 3.12 — stable versions instead of 3.14
PYTHON_CMD=""
for v in python3.12 python3.11 python3; do
    if command -v "$v" &>/dev/null; then
        PYTHON_CMD="$v"
        break
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo -e "${RED}Error: Python 3.11+ not found!${NC}"
    echo "Install it with: sudo apt install python3.12"
    exit 1
fi
PYTHON_VERSION=$($PYTHON_CMD --version 2>&1)
echo -e "${GREEN}✅ $PYTHON_VERSION found ($PYTHON_CMD)${NC}"

echo ""
echo -e "${YELLOW}================================================${NC}"
echo -e "${YELLOW}  SynthAI Configuration${NC}"
echo -e "${YELLOW}================================================${NC}"
echo ""

# Ask for API keys
echo -e "${CYAN}Step 1: Gemini API keys${NC}"
echo "Get a free key at: https://aistudio.google.com"
echo ""
read -p "Enter GEMINI_API_KEY (main): " GEMINI_KEY
while [ -z "$GEMINI_KEY" ]; do
    echo -e "${RED}The key cannot be empty!${NC}"
    read -p "Enter GEMINI_API_KEY: " GEMINI_KEY
done

read -p "Enter GEMINI_RESEARCH_API_KEY (second account, or the same one): " GEMINI_RESEARCH_KEY
if [ -z "$GEMINI_RESEARCH_KEY" ]; then
    GEMINI_RESEARCH_KEY=$GEMINI_KEY
    echo "Using the same key for the researcher."
fi

echo ""
echo -e "${CYAN}Step 2: OBD adapter${NC}"
echo "MAC address of your Bluetooth OBD adapter"
echo "Example: AA:BB:CC:11:22:33"
echo "(Find it with: bluetoothctl scan on)"
echo ""
read -p "Enter the OBD adapter MAC address: " OBD_MAC
while [ -z "$OBD_MAC" ]; do
    echo -e "${RED}The MAC address cannot be empty!${NC}"
    read -p "Enter the MAC address: " OBD_MAC
done

echo ""
echo -e "${CYAN}Step 3: Username${NC}"
CURRENT_USER=$(whoami)
read -p "Ubuntu username [$CURRENT_USER]: " INPUT_USER
USER_NAME=${INPUT_USER:-$CURRENT_USER}
HOME_DIR="/home/$USER_NAME"
INSTALL_DIR="$HOME_DIR/autodiag"

echo ""
echo -e "${YELLOW}================================================${NC}"
echo -e "${YELLOW}  Confirm settings${NC}"
echo -e "${YELLOW}================================================${NC}"
echo "  User:          $USER_NAME"
echo "  Directory:     $INSTALL_DIR"
echo "  OBD MAC:       $OBD_MAC"
echo "  Python:        $PYTHON_CMD ($PYTHON_VERSION)"
echo "  Gemini key:    ${GEMINI_KEY:0:20}..."
echo ""
read -p "Continue with installation? (y/n): " CONFIRM
if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
    echo "Installation cancelled."
    exit 0
fi

echo ""
echo -e "${YELLOW}[1/9] Updating system...${NC}"
sudo apt update -y 2>/dev/null
echo -e "${GREEN}✅ System updated${NC}"

echo -e "${YELLOW}[2/9] Installing system packages...${NC}"
# FIXED: removed mono-complete (500 MB of unnecessary package)
sudo apt install -y \
    bluetooth bluez bluez-tools \
    pipewire pipewire-pulse wireplumber \
    libspa-0.2-bluetooth \
    alsa-utils \
    portaudio19-dev libportaudio2 \
    ffmpeg \
    xorg xinit openbox \
    firefox \
    git curl wget 2>/dev/null
echo -e "${GREEN}✅ Packages installed${NC}"

echo -e "${YELLOW}[3/9] Configuring Bluetooth...${NC}"
sudo systemctl enable bluetooth
sudo systemctl start bluetooth

echo "options btusb enable_autosuspend=n" | sudo tee /etc/modprobe.d/btusb.conf > /dev/null
echo "options bluetooth disable_ertm=1" | sudo tee /etc/modprobe.d/bluetooth.conf > /dev/null

sudo bash -c 'cat > /etc/bluetooth/main.conf << EOF
[Policy]
AutoEnable=true

[General]
FastConnectable=true
ControllerMode=bredr
EOF'
echo -e "${GREEN}✅ Bluetooth configured${NC}"

echo -e "${YELLOW}[4/9] Installing Python dependencies...${NC}"
cd "$INSTALL_DIR"
$PYTHON_CMD -m venv venv
source venv/bin/activate

pip install --upgrade pip --quiet
pip install \
    flask \
    google-genai \
    python-dotenv \
    obd \
    pyserial \
    faster-whisper \
    edge-tts \
    pygame \
    pyaudio \
    numpy \
    SpeechRecognition \
    ollama --quiet
echo -e "${GREEN}✅ Python dependencies installed${NC}"

echo -e "${YELLOW}[5/9] Installing Ollama...${NC}"
curl -fsSL https://ollama.com/install.sh | sh 2>/dev/null
sleep 3
ollama pull gemma3:12b
echo -e "${GREEN}✅ Ollama and model installed${NC}"

echo -e "${YELLOW}[6/9] Writing configuration...${NC}"
# FIXED: OBD_MAC is now also written to .env, not just hardcoded
cat > "$INSTALL_DIR/.env" << EOF
GEMINI_API_KEY=$GEMINI_KEY
GEMINI_RESEARCH_API_KEY=$GEMINI_RESEARCH_KEY
OBD_MAC=$OBD_MAC
EOF
echo -e "${GREEN}✅ Configuration written to .env${NC}"

echo -e "${YELLOW}[7/9] Configuring autostart...${NC}"
sudo bash -c "cat > /etc/rc.local << EOF
#!/bin/bash
sleep 15
rmmod btusb 2>/dev/null
sleep 3
modprobe btusb
sleep 8
hciconfig hci0 up
sleep 3
bluetoothctl power on
sleep 2
bluetoothctl connect $OBD_MAC
sleep 5
rfcomm connect 0 $OBD_MAC 1 &
sleep 8
chmod 666 /dev/rfcomm0 2>/dev/null
exit 0
EOF"
sudo chmod +x /etc/rc.local
sudo systemctl enable rc-local

mkdir -p "$HOME_DIR/.config/openbox"
cat > "$HOME_DIR/.config/openbox/autostart" << EOF
pulseaudio --start &
setxkbmap -layout us,ua &
sleep 5
cd $INSTALL_DIR && source venv/bin/activate && $PYTHON_CMD app.py &
sleep 3
firefox --kiosk http://localhost:5000 &
EOF

cat >> "$HOME_DIR/.bash_profile" << EOF
if [ -z "\$DISPLAY" ] && [ "\$(tty)" = "/dev/tty1" ]; then
    startx openbox-session
fi
EOF
echo -e "${GREEN}✅ Autostart configured${NC}"

echo -e "${YELLOW}[8/9] Configuring sudoers...${NC}"
echo "$USER_NAME ALL=(ALL) NOPASSWD: /usr/bin/rfcomm, /bin/chmod, /sbin/hciconfig, /sbin/modprobe, /sbin/rmmod, /usr/bin/fuser" | sudo tee /etc/sudoers.d/synthai > /dev/null
sudo chmod 440 /etc/sudoers.d/synthai
echo -e "${GREEN}✅ Sudoers configured${NC}"

echo -e "${YELLOW}[9/9] Configuring autologin...${NC}"
sudo mkdir -p /etc/systemd/system/getty@tty1.service.d
sudo bash -c "cat > /etc/systemd/system/getty@tty1.service.d/autologin.conf << EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin $USER_NAME --noclear %I \$TERM
EOF"
sudo systemctl daemon-reload
echo -e "${GREEN}✅ Autologin configured${NC}"

echo ""
echo -e "${GREEN}"
echo "  ================================================"
echo "  🎉 SynthAI installed successfully!"
echo "  ================================================"
echo ""
echo "  After reboot, the system will automatically:"
echo "  • Connect to the OBD adapter ($OBD_MAC)"
echo "  • Launch the IRIS diagnostic stand"
echo "  • Open the interface in a browser"
echo ""
echo "  To launch manually:"
echo "  cd $INSTALL_DIR"
echo "  source venv/bin/activate"
echo "  $PYTHON_CMD app.py"
echo ""
echo -e "${NC}"

read -p "Reboot now? (y/n): " REBOOT
if [ "$REBOOT" = "y" ] || [ "$REBOOT" = "Y" ]; then
    sudo reboot
fi
