#!/bin/bash
# 🚀 Compact Deployer (deploy.sh)
set -e

PI_HOST="${PI_HOST:-"raspberrypi.local"}"
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
  --exclude="staging/" \
  --exclude="backups/" \
  --exclude="updates/" \
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
sudo mkdir -p "$PI_DIR/logs" "$PI_DIR/staging" "$PI_DIR/backups" "$PI_DIR/updates" /opt/music-player/media/{audio,video,images,thumbnails}
sudo chown -R "$PI_USER:$PI_USER" "$PI_DIR" /opt/music-player/media
sudo chmod 755 "$PI_DIR/logs"
sudo chmod 755 "$PI_DIR/staging" "$PI_DIR/backups" "$PI_DIR/updates"
# Clear any stale clone directories from previous failed updates
sudo rm -rf "$PI_DIR/staging/clone" "$PI_DIR/staging/extracted" "$PI_DIR/staging"/*

# --- AUDIO & HARDWARE CONFIGURATION ---
echo "-> Configuring USB & Audio (Card 2)..."
CONFIG_FILE="/boot/firmware/config.txt"
[ ! -f "$CONFIG_FILE" ] && CONFIG_FILE="/boot/config.txt"

# Ensure USB enumeration on boot (disable low-power mode)
if ! grep -q "dwc_otg.lpm_enable=0" "$CONFIG_FILE"; then
  echo "# USB enumeration fix for Pi 3 A+" | sudo tee -a "$CONFIG_FILE" > /dev/null
  echo "dtparam=usb_max_power_enable=1" | sudo tee -a "$CONFIG_FILE" > /dev/null
  echo "dtoverlay=dwc2" | sudo tee -a "$CONFIG_FILE" > /dev/null
fi

# 2. Configure Audio Output to Card 2 via .asoundrc
# Use plughw to automatically handle format conversion and resampling
# This is a proven, stable approach for USB audio on Raspberry Pi
cat <<CONFIG | sudo tee /home/$PI_USER/.asoundrc
pcm.!default {
    type plughw
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
  # Install ALSA plugins for plughw support, pulse/pipewire, and mpv for radio
  sudo apt-get install -y git python3-dev python3-venv build-essential libpulse0 pulseaudio-utils swig liblgpio-dev mpv libasound2-plugins
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
  pip install Flask werkzeug pillow pydantic qrcode requests >/dev/null 2>&1
  
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
# Remove any commented out SDL lines or old junk before copying
sed -i '/SDL_AUDIODRIVER/d' *.service
sed -i '/# Removed:/d' *.service
sed -i "s/User=pi/User=$PI_USER/g" *.service
sudo cp *.service /etc/systemd/system/
sudo systemctl daemon-reload

echo "-> Enabling services for startup..."
sudo systemctl enable music-player.service music-splash.service

if [ "$RESTART_SERVICE" = "true" ]; then
  echo "-> Restarting music-player and music-web services..."
  sudo systemctl restart music-player.service music-web.service
  echo "✅ Music services restarted successfully."
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

# Configure sudoers for web user to manage services without password
SUDOERS_LINE="$PI_USER ALL=(ALL) NOPASSWD: /opt/music-player/scripts/music-player-restart.sh, /bin/systemctl restart music-player, /bin/systemctl stop music-player, /bin/systemctl start music-player, /bin/systemctl status music-player, /bin/systemctl restart music-web, /bin/systemctl stop music-web, /bin/systemctl start music-web, /bin/systemctl status music-web, /bin/systemctl restart music-splash, /bin/systemctl stop music-splash, /bin/systemctl start music-splash, /bin/systemctl status music-splash, /usr/bin/journalctl, /usr/bin/vcgencmd"

# Check if sudoers entry already exists (check for a substring to see if update is needed)
if ! sudo grep -q "music-splash" /etc/sudoers.d/music-player 2>/dev/null; then
  echo "$SUDOERS_LINE" | sudo tee /etc/sudoers.d/music-player > /dev/null
  sudo chmod 440 /etc/sudoers.d/music-player
  echo "✓ Sudoers configured for $PI_USER"
else
  echo "✓ Sudoers already configured"
fi

echo "-> Update privileges configured"
EOF

echo "🚀 Deployment finished!"