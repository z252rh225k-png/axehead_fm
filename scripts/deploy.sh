#!/bin/bash
# 🚀 Compact Deployer (deploy.sh)
set -e

PI_HOST="${PI_HOST:-"raspberrypidev.local"}"
PI_USER="${PI_USER:-"user"}"
PI_DIR="${PI_DIR:-"/opt/music-player"}"

# Defaults: Running `./deploy.sh` handles everything automatically.
INSTALL_DEPS=true
RESTART_SERVICE=true
WEB_SETUP=true

while [[ $# -gt 0 ]]; do
  case $1 in
    -w|--web-setup) WEB_SETUP=true; shift ;;
    --skip-install) INSTALL_DEPS=false; shift ;;
    --skip-restart) RESTART_SERVICE=false; shift ;;
    -h|--host) PI_HOST="$2"; shift 2 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
REPO_ROOT="$( dirname "$SCRIPT_DIR" )"

# Ensure the target directory exists and is owned by the user BEFORE rsync runs
echo "🏗️  Preparing target directory on $PI_HOST..."
ssh -t "$PI_USER@$PI_HOST" "sudo mkdir -p $PI_DIR && sudo chown -R $PI_USER:$PI_USER $PI_DIR"

echo "📡 Syncing files to $PI_USER@$PI_HOST..."
rsync -avz --delete \
  --exclude="venv/" \
  --exclude=".git/" \
  --exclude="**/*.pyc" \
  --exclude="**/__pycache__/" \
  --exclude=".DS_Store" \
  --exclude=".vscode/" \
  --exclude=".idea/" \
  --exclude="*.bin" \
  --exclude="*.mp3" \
  --exclude="media/" \
  --exclude="logs/" \
  "$REPO_ROOT/" "$PI_USER@$PI_HOST:$PI_DIR/"

echo "⚙️  Executing remote configuration on Pi..."

# Bundle remaining operations into a single session
ssh -t "$PI_USER@$PI_HOST" "bash -s" -- "$PI_DIR" "$PI_USER" "$INSTALL_DEPS" "$RESTART_SERVICE" "$WEB_SETUP" << 'EOF'
set -e
PI_DIR="$1"
PI_USER="$2"
INSTALL_DEPS="$3"
RESTART_SERVICE="$4"
WEB_SETUP="$5"

echo "-> Finalizing folder layout..."
sudo mkdir -p "$PI_DIR/logs" /opt/music-player/media/{audio,video,images,thumbnails}
sudo chown -R "$PI_USER:$PI_USER" "$PI_DIR" /opt/music-player/media
sudo chmod 755 "$PI_DIR/logs"

# --- AUDIO & HARDWARE CONFIGURATION ---
echo "-> Configuring Audio (USB Card 2) & Cleaning Hardware Overlays..."
CONFIG_FILE="/boot/firmware/config.txt"
[ ! -f "$CONFIG_FILE" ] && CONFIG_FILE="/boot/config.txt"

# 1. Remove the DWC2 overlay (it breaks the Pi 3 A+ USB port)
sudo sed -i '/dtoverlay=dwc2/d' "$CONFIG_FILE"
sudo sed -i '/# Axehead FM USB Fix/d' "$CONFIG_FILE"

# 2. Force Audio Output to Card 2 via .asoundrc
cat <<CONFIG | sudo tee /home/$PI_USER/.asoundrc
pcm.!default {
  type hw
  card 2
}
ctl.!default {
  type hw
  card 2
}
CONFIG
sudo chown "$PI_USER:$PI_USER" /home/$PI_USER/.asoundrc
# --- END AUDIO CONFIGURATION ---

if [ "$INSTALL_DEPS" = "true" ]; then
  echo "-> Installing system dependencies..."
  sudo apt-get update
  sudo apt-get install -y python3-dev python3-venv build-essential libpulse0 pulseaudio-utils swig liblgpio-dev
  sudo raspi-config nonint do_i2c 0 && sudo raspi-config nonint do_serial_cons 1 && sudo raspi-config nonint do_serial_hw 0

  echo "-> Building virtual environment & installing Python packages..."
  cd "$PI_DIR"
  if [ ! -d "venv" ]; then
    python3 -m venv venv
  fi
  source venv/bin/activate
  pip install --upgrade pip >/dev/null 2>&1
  pip install -e .
fi

if [ "$WEB_SETUP" = "true" ]; then
  echo "-> Provisioning Web UI..."
  cd "$PI_DIR"
  if [ ! -d "venv" ]; then
    python3 -m venv venv
  fi
  source venv/bin/activate
  pip install Flask werkzeug pillow pydantic qrcode >/dev/null 2>&1
  
  if [ ! -f catalog.json ]; then
    echo '{}' > catalog.json
    chown "$PI_USER:$PI_USER" catalog.json
  fi
  
  cat > run_web.sh <<SCRIPT
#!/bin/bash
cd $PI_DIR
exec $PI_DIR/venv/bin/python -c 'from music_player.web.app import create_app; create_app().run(host="0.0.0.0", port=5000, debug=False)'
SCRIPT
  chmod +x run_web.sh
  
  sudo tee /etc/systemd/system/music-web.service > /dev/null <<UNIT
[Unit]
Description=Axehead FM Web Interface
After=network.target

[Service]
Type=simple
User=$PI_USER
WorkingDirectory=$PI_DIR
ExecStart=$PI_DIR/run_web.sh
Restart=on-failure
StandardOutput=journal

[Install]
WantedBy=multi-user.target
UNIT
  sudo systemctl daemon-reload
  sudo systemctl enable --now music-web.service
fi

echo "-> Updating systemd services..."
cd "$PI_DIR/systemd"
sed -i "s/User=pi/User=$PI_USER/g" *.service
sudo cp *.service /etc/systemd/system/
sudo systemctl daemon-reload

echo "-> Enabling services for startup..."
sudo systemctl enable music-player.service music-splash.service

if [ "$RESTART_SERVICE" = "true" ]; then
  echo "-> Restarting music-player service..."
  sudo systemctl restart music-player.service
  echo "✅ Service restarted successfully."
fi

# --- PRIVILEGE ESCALATION SETUP FOR UPDATES ---
echo "-> Setting up privileged update helper..."

# Copy restart helper script
mkdir -p "$PI_DIR/scripts"
# Make restart helper script executable (already synced via rsync)
if [ -f "$PI_DIR/scripts/music-player-restart.sh" ]; then
  chmod +x "$PI_DIR/scripts/music-player-restart.sh"
  echo "✓ Restart helper is executable"
else
  echo "⚠️ Warning: Restart helper script not found"
fi

# Configure sudoers for web user to restart service without password
SUDOERS_LINE="$PI_USER ALL=(ALL) NOPASSWD: /opt/music-player/scripts/music-player-restart.sh, /bin/systemctl restart music-player, /bin/systemctl status music-player"

# Check if sudoers entry already exists
if ! sudo grep -q "music-player-restart.sh" /etc/sudoers.d/music-player 2>/dev/null; then
  echo "$SUDOERS_LINE" | sudo tee /etc/sudoers.d/music-player > /dev/null
  sudo chmod 440 /etc/sudoers.d/music-player
  echo "✓ Sudoers configured for $PI_USER"
else
  echo "✓ Sudoers already configured"
fi

echo "-> Update privileges configured"
EOF

echo "🚀 Deployment finished!"