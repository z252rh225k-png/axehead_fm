import subprocess
import re
import threading
import time

class BluetoothManager:
    """
    Manages scanning, connecting, disconnecting, and tracking the status of
    Bluetooth devices on Raspberry Pi using the CLI `bluetoothctl` wrapper.
    It runs scanning and status checks in background threads to avoid blocking
    the main OLED/NFC loop.
    """
    def __init__(self):
        self.discovered_devices = []  # List of dicts: {'mac': ..., 'name': ...}
        self.connected_device = None   # None or dict: {'mac': ..., 'name': ...}
        self.is_scanning = False
        self._scan_thread = None
        self._status_thread = None
        self._stop_threads = False

        # Start background check for current connection status
        self.start_status_monitor()

    def start_status_monitor(self):
        """Starts a background thread to keep connection status updated."""
        self._stop_threads = False
        self._status_thread = threading.Thread(target=self._monitor_status_loop, daemon=True)
        self._status_thread.start()

    def stop_monitors(self):
        """Cleanly stops background loops."""
        self._stop_threads = True
        self.stop_scan()

    def _run_cmd(self, args):
        """Helper to run command and return output."""
        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=5)
            return result.stdout
        except Exception as e:
            print(f"[BT Manager] Command error {args}: {e}")
            return ""

    def _monitor_status_loop(self):
        """Periodically checks if a bluetooth audio sink is connected."""
        while not self._stop_threads:
            # Check bluetoothctl info to find connected audio/headset profiles
            info = self._run_cmd(["bluetoothctl", "info"])
            # Or check standard devices
            # A more reliable way: check paired/connected devices list
            connected_mac = None
            connected_name = "Unknown Device"
            
            # Let's list devices and see which is connected
            devices_out = self._run_cmd(["bluetoothctl", "devices"])
            for line in devices_out.splitlines():
                match = re.search(r"Device ([0-9A-F:]+) (.*)", line)
                if match:
                    mac, name = match.group(1), match.group(2)
                    # Check detailed info for this MAC to verify connection
                    device_info = self._run_cmd(["bluetoothctl", "info", mac])
                    if "Connected: yes" in device_info:
                        connected_mac = mac
                        connected_name = name
                        break
            
            if connected_mac:
                self.connected_device = {"mac": connected_mac, "name": connected_name}
            else:
                self.connected_device = None
            
            time.sleep(3.0) # Check every 3 seconds

    def start_scan(self):
        """Starts bluetoothctl scanning in a separate thread."""
        if self.is_scanning:
            return
        self.is_scanning = True
        self._scan_thread = threading.Thread(target=self._scan_loop, daemon=True)
        self._scan_thread.start()

    def stop_scan(self):
        """Stops the scanning operation."""
        if not self.is_scanning:
            return
        self.is_scanning = False
        # Tell bluetoothctl to stop scanning
        subprocess.run(["bluetoothctl", "scan", "off"], capture_output=True)

    def _scan_loop(self):
        """Triggers bluetoothctl scan and updates the discovered devices list."""
        # Enable scan
        subprocess.run(["bluetoothctl", "scan", "on"], capture_output=True)
        
        while self.is_scanning and not self._stop_threads:
            # Query currently discovered devices
            devices_out = self._run_cmd(["bluetoothctl", "devices"])
            new_devices = []
            for line in devices_out.splitlines():
                match = re.search(r"Device ([0-9A-F:]+) (.*)", line)
                if match:
                    mac, name = match.group(1), match.group(2)
                    # Exclude generic non-name/phone tags or just keep recognizable ones
                    if name and not name.startswith("LG") and not name.startswith("TX-") and ":" not in name:
                        new_devices.append({"mac": mac, "name": name})
            
            self.discovered_devices = new_devices
            time.sleep(2.0)

    def connect_device(self, mac):
        """Pairs, trusts, and connects to a bluetooth MAC address."""
        print(f"[BT Manager] Attempting to connect to {mac}...")
        
        # Stop scanning first so Bluetooth chip can focus on connection
        self.stop_scan()
        
        # Run standard pairing sequences
        self._run_cmd(["bluetoothctl", "pair", mac])
        self._run_cmd(["bluetoothctl", "trust", mac])
        out = self._run_cmd(["bluetoothctl", "connect", mac])
        
        # Verify connection success
        success = "Connection successful" in out or "Connection: yes" in self._run_cmd(["bluetoothctl", "info", mac])
        return success

    def disconnect_device(self, mac):
        """Disconnects a Bluetooth device."""
        print(f"[BT Manager] Disconnecting {mac}...")
        self._run_cmd(["bluetoothctl", "disconnect", mac])
        self.connected_device = None
        return True
