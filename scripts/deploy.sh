#!/bin/bash

# ==============================================================================
# 🚀 Raspberry Pi Music Player Code Deployer (deploy.sh)
# ==============================================================================
# This script rsyncs local changes from your macOS machine to your Raspberry Pi
# in near real-time, eliminating the need to commit & push to GitHub to test.
#
# Requirements:
# - SSH key authentication configured between macOS and the Pi.
# - rsync installed on your mac (run `brew install rsync` if missing).
# ==============================================================================

# Exit on error
set -e

# Default Pi configuration - override with environment variables or arguments
PI_HOST="${PI_HOST:-"raspberrypi.local"}"
PI_USER="${PI_USER:-"user"}"
PI_DIR="${PI_DIR:-"/opt/music-player"}"

# Help message
show_help() {
  echo "Usage: ./scripts/deploy.sh [OPTIONS]"
  echo ""
  echo "Options:"
  echo "  -h, --host HOST      IP or hostname of the Raspberry Pi (default: $PI_HOST)"
  echo "  -u, --user USER      SSH user on the Raspberry Pi (default: $PI_USER)"
  echo "  -d, --dir DIR        Destination directory on the Pi (default: $PI_DIR)"
  echo "  -r, --restart        Restart the music-player service after syncing"
  echo "  -s, --status         Check the systemd service status after syncing"
  echo "  --help               Show this help message"
  echo ""
  echo "Examples:"
  echo "  ./scripts/deploy.sh"
  echo "  ./scripts/deploy.sh -h 192.168.1.150 -r"
  echo "  PI_HOST=192.168.1.150 ./scripts/deploy.sh -r"
}

RESTART_SERVICE=false
CHECK_STATUS=false

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    -h|--host)
      PI_HOST="$2"
      shift 2
      ;;
    -u|--user)
      PI_USER="$2"
      shift 2
      ;;
    -d|--dir)
      PI_DIR="$2"
      shift 2
      ;;
    -r|--restart)
      RESTART_SERVICE=true
      shift
      ;;
    -s|--status)
      CHECK_STATUS=true
      shift
      ;;
    --help)
      show_help
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      show_help
      exit 1
      ;;
  esac
done

# Check if rsync is installed locally
if ! command -v rsync &> /dev/null; then
  echo "❌ Error: rsync is not installed on this machine."
  echo "   If you are on macOS, run: brew install rsync"
  exit 1
fi

# Print deployment info
echo "=============================================================================="
echo "📡 Deploying axehead_fm to Raspberry Pi..."
echo "=============================================================================="
echo "👤 Target User: $PI_USER"
echo "🖥️  Target Host: $PI_HOST"
echo "📂 Target Dir:  $PI_DIR"
echo "=============================================================================="

# Test connection with a fast SSH probe
echo "[*] Verifying SSH connection to $PI_USER@$PI_HOST..."
if ! ssh -o ConnectTimeout=3 -q "$PI_USER@$PI_HOST" exit; then
  echo "❌ Error: Could not connect to $PI_USER@$PI_HOST over SSH."
  echo "   Please check:"
  echo "   1. Is your Pi connected to the network?"
  echo "   2. Is SSH enabled on the Pi?"
  echo "   3. Have you added your SSH public key to the Pi's authorized_keys file?"
  echo "      Try running: ssh-copy-id $PI_USER@$PI_HOST"
  exit 1
fi
echo "✅ SSH connection verified."

# Prepare target directories on the Pi
echo "[*] Creating necessary directories on $PI_HOST..."
ssh "$PI_USER@$PI_HOST" "sudo mkdir -p $PI_DIR && sudo chown -R $PI_USER:$PI_USER $PI_DIR && sudo mkdir -p $PI_DIR/logs && sudo chown $PI_USER:$PI_USER $PI_DIR/logs && sudo chmod 755 $PI_DIR/logs" || true
echo "✅ Directories ready."

# Sync files using rsync
# -a: archive mode (preserves permissions, symlinks, modification times)
# -v: verbose output
# -z: compress file data during the transfer
# --delete: delete extraneous files from destination directory (mirroring)
echo "[*] Syncing files..."
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
  ./ "$PI_USER@$PI_HOST:$PI_DIR/"

echo "✅ Sync complete."

# Ensure logs directory exists after sync (rsync --delete won't remove it now, but let's verify)
echo "[*] Verifying logs directory exists on $PI_HOST..."
ssh "$PI_USER@$PI_HOST" "sudo mkdir -p $PI_DIR/logs && sudo chown $PI_USER:$PI_USER $PI_DIR/logs && sudo chmod 755 $PI_DIR/logs && ls -ld $PI_DIR/logs" || true
echo "✅ Logs directory confirmed."

# Copy updated systemd service files to /etc/systemd/system/
echo "[*] Installing updated systemd service files on $PI_HOST..."
# Verify files exist first
ssh "$PI_USER@$PI_HOST" "ls -la $PI_DIR/systemd/" || {
  echo "❌ Error: systemd files not found at $PI_DIR/systemd/"
  exit 1
}
# Replace User=pi with the actual SSH user (same as install.sh does)
ssh "$PI_USER@$PI_HOST" "sed -i 's/User=pi/User=$PI_USER/g' $PI_DIR/systemd/music-player.service && sudo cp $PI_DIR/systemd/music-player.service /etc/systemd/system/ && sudo cp $PI_DIR/systemd/music-splash.service /etc/systemd/system/"
echo "✅ Service files installed."

# Restart music-player service if requested
if [ "$RESTART_SERVICE" = true ]; then
  echo "[*] Reloading systemd daemon on $PI_HOST to pick up updated service file..."
  ssh "$PI_USER@$PI_HOST" "sudo systemctl daemon-reload"
  echo "[*] Restarting music-player systemd service on $PI_HOST..."
  ssh -t "$PI_USER@$PI_HOST" "sudo systemctl restart music-player.service"
  echo "✅ Service restarted."
fi

# Check systemd status if requested
if [ "$CHECK_STATUS" = true ]; then
  echo "[*] Checking service status on $PI_HOST..."
  ssh "$PI_USER@$PI_HOST" "systemctl status music-player.service"
fi

echo "=============================================================================="
echo "🚀 Deployment successfully completed!"
echo "=============================================================================="
