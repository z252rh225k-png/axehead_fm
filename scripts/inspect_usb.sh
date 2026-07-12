#!/bin/bash
# Usage: ./inspect_usb.sh <hostname>

echo "--- Inspecting USB Hardware on $1 ---"

# 1. Check if the device is physically present on the bus
echo "[1/3] Checking USB Bus status..."
ssh user@$1 "lsusb -t"

# 2. Check kernel logs for USB handshake errors
echo "[2/3] Checking Kernel USB Handshake logs..."
ssh user@$1 "dmesg | grep -i 'usb' | tail -n 20"

# 3. Check for specific audio device driver binding
echo "[3/3] Checking if sound driver is bound to hardware..."
ssh user@$1 "ls -l /sys/bus/usb/drivers/snd-usb-audio/"

echo "--- Inspection Complete ---"