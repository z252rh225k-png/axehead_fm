# Phase 2: WiFi Setup via NFC

## Overview

Enable scanning NFC tags to provision WiFi credentials automatically. User creates an NFC tag with SSID/password encoded, then scans it and the Raspberry Pi connects to the network.

### Current implementation status (2026-07-04)
- Added a small `nmcli`-based network wrapper for Wi-Fi connection attempts.
- Added NFC payload parsing for simple `ssid=...|pass=...|auth=...` tags.
- Wired the player loop to try Wi-Fi provisioning when it sees a Wi-Fi-style NFC payload.
- Remaining polish: a fuller on-screen status screen and persisted provisioning UI.

**Time Estimate**: 2-3 days
**Dependencies**: nmcli (pre-installed on Raspberry Pi OS), optionally ndeflib

---

## Architecture

### NFC Tag Format

NDEF (NFC Data Exchange Format) message containing WiFi credentials:

```
NDEF Message
├── Record Type: "application/x-wifi"
├── Payload: TLV-encoded data
│   ├── TLV 0x10: SSID length + value
│   ├── TLV 0x27: Network Key (password) length + value
│   └── TLV 0x0F: Auth Type (0x02 = WPA2)
```

**Simple format** (for prototyping):
```
TAG_ID: "nfc_wifi_provision"
Payload: "ssid=MyNetwork|pass=MyPassword123|auth=WPA2"
```

### Directory Structure

```
src/music_player/
├── hardware/
│   ├── nfc_reader.py          (EXTEND existing)
│   │   └── Add: is_wifi_tag(), parse_wifi_ndef()
│   └── network_manager.py     (NEW)
│       ├── connect_wifi(ssid, password, security)
│       ├── is_connected()
│       ├── get_network_status()
│       └── start_hotspot()
├── state/
│   └── config.py              (EXTEND)
│       └── Add: WIFI_CONFIG, HOTSPOT_SSID
├── ui/screens/
│   └── wifi_setup_screen.py   (NEW)
│       └── Render WiFi connection progress
└── handlers/
    └── wifi_handler.py        (NEW - optional)
        └── Handle WiFi provisioning as special mode
```

---

## Implementation: Step by Step

### Step 1: Network Manager Wrapper

```python
# src/music_player/hardware/network_manager.py

import subprocess
import time
import socket
from typing import Tuple, Optional
from pathlib import Path
import json

class NetworkManager:
    """Interface with NetworkManager via nmcli."""
    
    def __init__(self):
        self.connected = False
        self.current_ssid = None
        self.current_ip = None
        self.hotspot_active = False
    
    def connect_wifi(self, ssid: str, password: str, 
                     security: str = "WPA2") -> Tuple[bool, str]:
        """Connect to WiFi network.
        
        Args:
            ssid: Network name
            password: WPA2 passphrase
            security: "WPA2" or "WPA3"
        
        Returns:
            (success, message)
        """
        try:
            # Disconnect from any existing networks
            subprocess.run(["nmcli", "radio", "wifi", "on"], 
                          check=False, capture_output=True)
            
            # Attempt connection
            result = subprocess.run([
                "nmcli", "device", "wifi", "connect", ssid,
                "password", password
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                # Wait for connection to stabilize
                time.sleep(5)
                
                # Verify connection
                if self._verify_connection(ssid):
                    self.connected = True
                    self.current_ssid = ssid
                    self.current_ip = self._get_local_ip()
                    return True, f"Connected to {ssid}"
                else:
                    return False, "Failed to verify connection"
            else:
                return False, f"Connection failed: {result.stderr}"
        
        except subprocess.TimeoutExpired:
            return False, "Connection timeout"
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    def disconnect(self) -> bool:
        """Disconnect from WiFi."""
        try:
            subprocess.run(["nmcli", "radio", "wifi", "off"],
                          check=True, capture_output=True)
            self.connected = False
            self.current_ssid = None
            return True
        except Exception as e:
            print(f"Disconnect failed: {e}")
            return False
    
    def start_hotspot(self, ssid: str = "AxeheadFM", 
                     password: str = "pi1234567") -> Tuple[bool, str]:
        """Start WiFi hotspot for provisioning."""
        try:
            # Create hotspot connection
            subprocess.run([
                "nmcli", "device", "wifi", "hotspot",
                "ifname", "wlan0",
                "ssid", ssid,
                "password", password
            ], check=True, capture_output=True, timeout=15)
            
            time.sleep(3)
            
            if self._verify_hotspot():
                self.hotspot_active = True
                return True, f"Hotspot '{ssid}' started"
            else:
                return False, "Hotspot failed to start"
        
        except Exception as e:
            return False, f"Hotspot error: {str(e)}"
    
    def stop_hotspot(self) -> bool:
        """Stop WiFi hotspot."""
        try:
            subprocess.run(["nmcli", "radio", "wifi", "off"],
                          check=True, capture_output=True)
            self.hotspot_active = False
            return True
        except Exception as e:
            print(f"Stop hotspot failed: {e}")
            return False
    
    def is_connected(self) -> bool:
        """Check if connected to internet."""
        try:
            # Test connectivity to 8.8.8.8 (Google DNS)
            socket.create_connection(("8.8.8.8", 53), timeout=2)
            return True
        except (socket.timeout, socket.error):
            return False
    
    def get_status(self) -> dict:
        """Get current network status."""
        try:
            result = subprocess.run(
                ["nmcli", "-t", "-f", "ACTIVE,SSID,SIGNAL", "device", "wifi", "list"],
                capture_output=True, text=True
            )
            
            # Parse output: yes|MyNetwork|85
            lines = result.stdout.strip().split('\n')
            connected = None
            for line in lines:
                if line.startswith('yes'):
                    parts = line.split('|')
                    if len(parts) >= 2:
                        connected = parts[1]
                    break
            
            return {
                'connected': self.is_connected(),
                'ssid': connected or self.current_ssid,
                'ip': self._get_local_ip(),
                'hotspot': self.hotspot_active
            }
        except Exception as e:
            print(f"Status check error: {e}")
            return {'connected': False, 'ssid': None, 'ip': None}
    
    def _verify_connection(self, ssid: str, timeout: int = 10) -> bool:
        """Verify we're connected to SSID."""
        start = time.time()
        while time.time() - start < timeout:
            try:
                result = subprocess.run(
                    ["nmcli", "-t", "-f", "ACTIVE,SSID", "device", "wifi", "list"],
                    capture_output=True, text=True, timeout=5
                )
                if ssid in result.stdout and 'yes' in result.stdout:
                    return True
            except Exception:
                pass
            time.sleep(1)
        return False
    
    def _verify_hotspot(self, timeout: int = 10) -> bool:
        """Verify hotspot is active."""
        start = time.time()
        while time.time() - start < timeout:
            try:
                result = subprocess.run(
                    ["nmcli", "device", "show", "wlan0"],
                    capture_output=True, text=True, timeout=5
                )
                if "hotspot" in result.stdout.lower():
                    return True
            except Exception:
                pass
            time.sleep(1)
        return False
    
    @staticmethod
    def _get_local_ip() -> Optional[str]:
        """Get local IP address."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return None


# Global instance
_network_manager = None

def get_network_manager() -> NetworkManager:
    """Singleton accessor."""
    global _network_manager
    if _network_manager is None:
        _network_manager = NetworkManager()
    return _network_manager
```

### Step 2: Extend NFC Reader

```python
# src/music_player/hardware/nfc_reader.py
# ADD these functions to existing nfc_reader.py

import re
from typing import Optional, Dict

def is_wifi_tag(tag_id: str, payload: str) -> bool:
    """Check if NFC tag is WiFi provisioning tag."""
    # Look for WiFi format markers
    return (
        tag_id.startswith("nfc_wifi") or
        "ssid=" in payload.lower() or
        "wifi" in tag_id.lower()
    )

def parse_wifi_ndef(payload: str) -> Optional[Dict[str, str]]:
    """Parse WiFi credentials from NDEF payload.
    
    Supported formats:
    - Simple: "ssid=NetworkName|pass=Password123|auth=WPA2"
    - Pipe separated: "SSID|PASSWORD"
    
    Args:
        payload: Raw NDEF record payload
    
    Returns:
        {'ssid': '...', 'password': '...', 'security': 'WPA2'} or None
    """
    try:
        # Try pipe-separated format first (simplest)
        if '|' in payload and 'ssid=' not in payload.lower():
            parts = payload.split('|')
            if len(parts) >= 2:
                return {
                    'ssid': parts[0].strip(),
                    'password': parts[1].strip(),
                    'security': 'WPA2'
                }
        
        # Try key=value format
        wifi_config = {
            'ssid': None,
            'password': None,
            'security': 'WPA2'
        }
        
        # Parse key=value pairs
        pairs = re.findall(r'([a-z]+)=([^|]+)', payload, re.IGNORECASE)
        
        for key, value in pairs:
            key_lower = key.lower()
            if key_lower in ['ssid', 'network']:
                wifi_config['ssid'] = value.strip()
            elif key_lower in ['pass', 'password', 'key']:
                wifi_config['password'] = value.strip()
            elif key_lower in ['auth', 'security', 'type']:
                wifi_config['security'] = value.strip().upper()
        
        # Validate we got required fields
        if wifi_config['ssid'] and wifi_config['password']:
            return wifi_config
        
        return None
    
    except Exception as e:
        print(f"WiFi NDEF parse error: {e}")
        return None

def read_tag_with_timeout(timeout_seconds: float = 0.05) -> Optional[Dict]:
    """Read NFC tag (existing function - no changes needed).
    
    This should return something like:
    {
        'uid': 'ABC123DEF456',
        'ndef_message': 'ssid=MyNetwork|pass=MyPassword',
        'type': 'text'  # or 'ndef'
    }
    """
    # Existing implementation
    pass
```

### Step 3: WiFi Setup Screen

```python
# src/music_player/ui/screens/wifi_setup_screen.py

from luma.core.render import canvas
from PIL import ImageDraw, ImageFont
import time

class WiFiSetupScreen:
    """Display for WiFi setup process."""
    
    def __init__(self, font_path: str = None):
        self.font = None
        if font_path:
            try:
                self.font = ImageFont.truetype(font_path, 10)
            except:
                pass
        self.start_time = time.time()
        self.status = "scanning"  # scanning, connecting, connected, error
        self.message = ""
    
    def render(self, display) -> None:
        """Render WiFi setup screen to display."""
        with canvas(display) as img:
            draw = ImageDraw.Draw(img)
            
            if self.status == "scanning":
                self._render_scanning(draw)
            elif self.status == "connecting":
                self._render_connecting(draw)
            elif self.status == "connected":
                self._render_connected(draw)
            elif self.status == "error":
                self._render_error(draw)
    
    def _render_scanning(self, draw: ImageDraw.ImageDraw) -> None:
        """Render scanning state."""
        draw.text((10, 10), "WiFi Setup", fill="white", font=self.font)
        draw.text((10, 25), "Waiting for NFC tag...", fill="white", font=self.font)
        
        # Animated dots
        dots = "." * (int(time.time()) % 4)
        draw.text((80, 40), dots, fill="white", font=self.font)
    
    def _render_connecting(self, draw: ImageDraw.ImageDraw) -> None:
        """Render connecting state."""
        draw.text((10, 10), "Connecting...", fill="white", font=self.font)
        draw.text((10, 25), self.message[:25], fill="white", font=self.font)
        
        # Progress bar
        progress = int((time.time() - self.start_time) * 20) % 100
        bar_width = int(progress / 100 * 100)
        draw.rectangle((10, 45, 118, 50), outline="white")
        draw.rectangle((10, 45, 10 + bar_width, 50), fill="white")
    
    def _render_connected(self, draw: ImageDraw.ImageDraw) -> None:
        """Render success state."""
        draw.text((10, 10), "Connected!", fill="white", font=self.font)
        draw.text((10, 25), f"SSID: {self.message[:20]}", fill="white", font=self.font)
        draw.text((10, 40), "Ready to play!", fill="white", font=self.font)
    
    def _render_error(self, draw: ImageDraw.ImageDraw) -> None:
        """Render error state."""
        draw.text((10, 10), "Connection Error", fill="white", font=self.font)
        draw.text((10, 25), self.message[:25], fill="white", font=self.font)
        draw.text((10, 45), "Restart to retry", fill="white", font=self.font)
    
    def set_status(self, status: str, message: str = "") -> None:
        """Update status display."""
        self.status = status
        self.message = message
        self.start_time = time.time()
```

### Step 4: Integration with Main Player Loop

Add to `player.py` main() function before the normal handler loop:

```python
# In src/music_player/player.py, around line 138 in main_player_loop()

from music_player.hardware.network_manager import get_network_manager
from music_player.hardware.nfc_reader import is_wifi_tag, parse_wifi_ndef
from music_player.ui.screens.wifi_setup_screen import WiFiSetupScreen

def main():
    """Main player entry point."""
    # ... existing initialization ...
    
    network_manager = get_network_manager()
    wifi_screen = WiFiSetupScreen()
    wifi_provisioning_active = False
    
    while True:
        try:
            # Check for NFC tag
            tag = nfc_reader.read_tag_with_timeout(0.05)
            
            if tag:
                # Check if it's a WiFi provisioning tag
                if is_wifi_tag(tag.get('uid', ''), tag.get('ndef_message', '')):
                    wifi_creds = parse_wifi_ndef(tag['ndef_message'])
                    
                    if wifi_creds:
                        wifi_provisioning_active = True
                        wifi_screen.set_status("connecting", wifi_creds['ssid'])
                        
                        # Attempt connection
                        success, msg = network_manager.connect_wifi(
                            wifi_creds['ssid'],
                            wifi_creds['password'],
                            wifi_creds.get('security', 'WPA2')
                        )
                        
                        if success:
                            wifi_screen.set_status("connected", wifi_creds['ssid'])
                            print(f"✅ WiFi connected: {wifi_creds['ssid']}")
                            time.sleep(5)  # Show success for 5 seconds
                            wifi_provisioning_active = False
                        else:
                            wifi_screen.set_status("error", msg)
                            print(f"❌ WiFi failed: {msg}")
                            time.sleep(5)
                            wifi_provisioning_active = False
                
                # Handle normal media tags only if not provisioning
                elif not wifi_provisioning_active:
                    # Existing tag handler code
                    handle_media_tag(tag)
            
            # Render appropriate screen
            if wifi_provisioning_active:
                wifi_screen.render(display)
            else:
                # Render normal UI
                uiRenderer.render(display, player_state, assets)
            
            # Sleep cycle
            time.sleep(0.1)
        
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error in main loop: {e}")
```

### Step 5: Configuration Update

```python
# In src/music_player/state/config.py, add:

# WiFi Configuration
WIFI_CONFIG_PATH = Path('/opt/music-player/wifi_config.json')
HOTSPOT_SSID = 'AxeheadFM'
HOTSPOT_PASSWORD = 'pi1234567'
HOTSPOT_CHANNEL = 6

def save_wifi_credentials(ssid: str, password: str) -> bool:
    """Save WiFi credentials to encrypted config."""
    try:
        config = {'ssid': ssid, 'password': password}
        with open(WIFI_CONFIG_PATH, 'w') as f:
            json.dump(config, f)
        # In production, encrypt this file
        return True
    except Exception as e:
        print(f"Failed to save WiFi config: {e}")
        return False

def load_wifi_credentials() -> dict:
    """Load saved WiFi credentials."""
    try:
        if WIFI_CONFIG_PATH.exists():
            with open(WIFI_CONFIG_PATH) as f:
                return json.load(f)
    except Exception as e:
        print(f"Failed to load WiFi config: {e}")
    return {'ssid': None, 'password': None}
```

---

## NFC Tag Creation

### Option 1: Using Phone App (Easiest)
- Download "NFC Tools" or "TagWriter" app
- Create new text record
- Set content to: `ssid=MyNetwork|pass=Password123|auth=WPA2`
- Write to blank NFC tag

### Option 2: Using nfcpy Library (Python)
```python
import nfc
from nfc.ndef import TextRecord, Message

def create_wifi_nfc_tag():
    """Create WiFi NFC tag."""
    wifi_text = "ssid=MyNetwork|pass=Password123|auth=WPA2"
    record = TextRecord(wifi_text, language='en')
    message = Message(record)
    
    # Write to tag using NFC reader
    with nfc.ContactlessFrontend() as clf:
        while True:
            tag = clf.poll(general=True)
            if tag:
                tag.ndef.message = message
                tag.ndef.save()
                print("WiFi tag created!")
                break
```

---

## Testing Checklist

### Local Setup
- [ ] Test WiFi connection manually: `nmcli device wifi connect SSID password PASSWORD`
- [ ] Test hotspot: `nmcli device wifi hotspot ssid AxeheadFM password pi1234567`
- [ ] Create test NFC tag with: `ssid=TESTNET|pass=TESTPASS`
- [ ] Verify parse_wifi_ndef() function works

### Integration Tests
- [ ] Create WiFi NFC tag
- [ ] Start player
- [ ] Scan WiFi tag
- [ ] Verify connection status in NetworkManager
- [ ] Check web interface shows connected
- [ ] Scan normal media tag - should work as before

### Error Cases
- [ ] Invalid SSID format (should show error screen)
- [ ] Wrong password (should show connection error)
- [ ] Tag with empty payload (should be ignored)
- [ ] Multiple rapid tags (should ignore duplicates)

---

## Troubleshooting

### nmcli not found
```bash
sudo apt update && sudo apt install network-manager
```

### Can't connect to WiFi
```bash
# Reset network
nmcli device disconnect wlan0
nmcli radio wifi on
# Try again
```

### Hotspot not working
- Ensure wlan0 is capable: `nmcli radio wifi`
- Check frequency availability in region
- Try different channel

---

## What's Next

After Phase 2 is complete, the player can:
- Auto-connect to saved WiFi on boot
- Act as hotspot if no WiFi available
- Ready for Phase 3 (GitHub updates over network)

Phase 3 will require WiFi connectivity to check for updates.
