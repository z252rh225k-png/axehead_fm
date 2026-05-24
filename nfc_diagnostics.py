import serial
import os
import re
import json
import time
from adafruit_pn532.uart import PN532_UART

print("======================================================================")
print("              Raspberry Pi Music Player - NFC DIAGNOSTICS            ")
print("======================================================================")

# 1. Initialize Reader
try:
    uart_device = serial.Serial("/dev/serial0", baudrate=115200, timeout=0.1)
    pn532 = PN532_UART(uart_device, debug=False)
    pn532.SAM_configuration()
    print("[+] NFC Reader successfully initialized on /dev/serial0.")
except Exception as e:
    print(f"[-] CRITICAL: NFC Reader initialization failed: {e}")
    print("    Check that UART is enabled and no other processes are locking it.")
    exit(1)

# 2. Check catalog.json
catalog_paths = ["/opt/music-player/catalog.json", "catalog.json"]
catalog = {}
active_catalog_path = None
for path in catalog_paths:
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                catalog = json.load(f)
                active_catalog_path = path
                break
        except Exception as e:
            print(f"[-] Error loading catalog {path}: {e}")

if active_catalog_path:
    print(f"[+] Loaded database from: {active_catalog_path}")
    print(f"    Available Keys in Catalog: {list(catalog.keys())}")
else:
    print("[-] WARNING: No catalog.json was found on the system!")

print("\n[*] Waiting for an NFC tag to be placed on the scanner...")

try:
    while True:
        uid = pn532.read_passive_target(timeout=0.5)
        if uid is not None:
            print("\n-------------------------------------------------------------")
            print(f"[+] Tag Detected! UID: {uid.hex()}")
            
            # Read Raw blocks
            raw_bytes = bytearray()
            print("[*] Reading raw blocks (4 to 20)...")
            for i in range(4, 20):
                block = pn532.ntag2xx_read_block(i)
                if block:
                    raw_bytes.extend(block)
            
            raw_text = raw_bytes.decode('ascii', errors='ignore')
            print(f"[+] Raw Text in memory:\n\"\"\"\n{raw_text}\n\"\"\"")
            
            # Resolve match using substring lookup on catalog keys
            matched_key = None
            for key in catalog.keys():
                if key in raw_text:
                    matched_key = key
                    break
            
            if matched_key:
                print(f"[+] MATCHED CATALOG KEY: \"{matched_key}\" (found inside raw text)")
                entry = catalog[matched_key]
                audio = entry.get("audio", "")
                image = entry.get("image", "")
                print(f"    - Title: {entry.get('title', 'N/A')}")
                print(f"    - Audio Path: \"{audio}\" -> {'[OK / EXISTS]' if os.path.exists(audio) else '[FILE NOT FOUND!]'}")
                print(f"    - Image Path: \"{image}\" -> {'[OK / EXISTS]' if os.path.exists(image) else '[FILE NOT FOUND!]'}")
            else:
                # Try fallback legacy path
                match_path = re.search(r'(/home/.*?\.mp3)', raw_text)
                if match_path:
                    legacy_path = match_path.group(1)
                    print(f"[+] Match found legacy path: \"{legacy_path}\"")
                    print(f"    - Path status: {'[OK / EXISTS]' if os.path.exists(legacy_path) else '[FILE NOT FOUND!]'}")
                else:
                    print("[-] No valid catalog keys or fallback .mp3 paths matched this tag content!")
            
            print("[*] Scan complete. Remove tag to scan again.")
            while pn532.read_passive_target(timeout=0.5) is not None:
                time.sleep(0.1)
            print("[*] Tag removed. Ready for next scan...")

except KeyboardInterrupt:
    print("\n[+] Diagnostics stopped cleanly.")