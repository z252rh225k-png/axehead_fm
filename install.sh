#!/bin/bash

# ==============================================================================
# Installer and Updater Script for Raspberry Pi Music Player
# ==============================================================================
# This script is idempotent. It can be run multiple times to install or upgrade
# the application, configure systemd, set up virtual environments, and check
# system hardware dependencies.
# ==============================================================================

set -e

INSTALL_DIR="/opt/music-player"

# Dynamically detect the real user who ran sudo, or default to the current active user
if [ -n "$SUDO_USER" ] && [ "$SUDO_USER" != "root" ]; then
  USER_NAME="$SUDO_USER"
else
  USER_NAME=$(logname 2>/dev/null || echo $USER)
fi

# Resolve group name (usually same as username)
GROUP_NAME=$(id -gn "$USER_NAME" 2>/dev/null || echo "$USER_NAME")

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo "[-] Please run as root (sudo ./install.sh or sudo bash install.sh)"
  exit 1
fi

echo "[+] Starting Music Player installation / update..."

# 1. System Dependencies
echo "[+] Updating apt repositories and installing system dependencies..."
apt-get update -y
apt-get install -y \
  python3 \
  python3-pip \
  python3-venv \
  python3-dev \
  git \
  libsdl2-mixer-2.0-0 \
  python3-pygame \
  i2c-tools \
  libjpeg-dev \
  zlib1g-dev \
  libfreetype6-dev \
  liblcms2-dev \
  libwebp-dev \
  tcl8.6-dev \
  tk8.6-dev \
  python3-tk \
  libharfbuzz-dev \
  libfribidi-dev \
  libxcb1-dev \
  python3-rpi.gpio \
  python3-lgpio \
  mpv

# 2. Re-enable interfaces if not already active
echo "[+] Enabling required hardware interfaces (I2C, SPI, Serial)..."
if ! grep -q "dtparam=i2c_arm=on" /boot/firmware/config.txt && ! grep -q "dtparam=i2c_arm=on" /boot/config.txt; then
  raspi-config nonint do_i2c 0 || echo "i2c_arm=on" >> /boot/firmware/config.txt || echo "i2c_arm=on" >> /boot/config.txt
fi

# Set safe high-speed 400kHz (Fast Mode) clock for smooth video rendering!
echo "[+] Configuring high-speed 400kHz I2C bus clock..."
if ! grep -q "i2c_arm_baudrate=400000" /boot/firmware/config.txt && ! grep -q "i2c_arm_baudrate=400000" /boot/config.txt; then
  # Append baudrate modifier to the active firmware config file
  if [ -f /boot/firmware/config.txt ]; then
    echo "dtparam=i2c_arm_baudrate=400000" >> /boot/firmware/config.txt
  else
    echo "dtparam=i2c_arm_baudrate=400000" >> /boot/config.txt
  fi
fi

if ! grep -q "enable_uart=1" /boot/firmware/config.txt && ! grep -q "enable_uart=1" /boot/config.txt; then
  raspi-config nonint do_serial_hw 0 || echo "enable_uart=1" >> /boot/firmware/config.txt || echo "enable_uart=1" >> /boot/config.txt
fi

# 3. Establish application folder
echo "[+] Copying application files to ${INSTALL_DIR}..."
mkdir -p "${INSTALL_DIR}"

# Copy all project files from current directory to installation directory
cp -R . "${INSTALL_DIR}/"

# Ensure user owns the installation directory
chown -R "${USER_NAME}:${GROUP_NAME}" "${INSTALL_DIR}"

# 4. Virtual Environment & Python Package Installation
echo "[+] Setting up Python virtual environment..."
if [ ! -d "${INSTALL_DIR}/venv" ]; then
  # Include system site packages so virtual environment can access system-level Compiled packages (like python3-lgpio / python3-rpi.gpio)
  sudo -u "${USER_NAME}" python3 -m venv --system-site-packages "${INSTALL_DIR}/venv"
fi

echo "[+] Upgrading pip and installing Python package..."
sudo -u "${USER_NAME}" "${INSTALL_DIR}/venv/bin/pip" install --upgrade pip wheel setuptools
sudo -u "${USER_NAME}" "${INSTALL_DIR}/venv/bin/pip" install -e "${INSTALL_DIR}"

# 4b. Create logs directory
echo "[+] Creating logs directory..."
mkdir -p "${INSTALL_DIR}/logs"
chown "${USER_NAME}:${GROUP_NAME}" "${INSTALL_DIR}/logs"
chmod 755 "${INSTALL_DIR}/logs"

# 5. systemd Service Setup
echo "[+] Copying and enabling systemd service files..."

# Check if the user 'pi' exists. If not, substitute with the current sudo caller
REAL_USER="${USER_NAME}"
sed -i "s/User=pi/User=${REAL_USER}/g" "${INSTALL_DIR}/systemd/music-player.service"

cp "${INSTALL_DIR}/systemd/music-player.service" /etc/systemd/system/
cp "${INSTALL_DIR}/systemd/music-splash.service" /etc/systemd/system/

echo "[+] Reloading systemd daemon..."
systemctl daemon-reload

echo "[+] Enabling services to start on boot..."
systemctl enable music-player.service
systemctl enable music-splash.service

# 6. Final Steps / Run
echo "[+] Starting services now..."
systemctl restart music-splash.service || true
systemctl restart music-player.service || true

echo "=============================================================================="
echo "[+] Installation & Update Complete!"
echo "    The music-player and music-splash services are now running in the background."
echo "    You can check status or logs using:"
echo "    - systemctl status music-player"
echo "    - journalctl -u music-player -f"
echo "    - tail -f /opt/music-player/logs/music-player.log"
echo "=============================================================================="
