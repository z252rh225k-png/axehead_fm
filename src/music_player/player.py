import time
import os
import re
import json
import pygame
import threading
import signal
import sys
import subprocess
import math
from gpiozero import Button
from PIL import Image

# Luma OLED imports
from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import sh1106

# NFC imports
import serial
from adafruit_pn532.uart import PN532_UART

# Bluetooth Integration
from music_player.bluetooth_manager import BluetoothManager

# Import Video preprocessed bin support from sibling module
from music_player.video_player import play_preprocessed_bin, play_video
from music_player.game_engine import run_snake_game

# ==========================================
# 1. HARDWARE & AUDIO INITIALIZATION
# ==========================================

# Initialize Audio Engine: Standard Pi audio parameter tweaks
# Try 44100Hz with a massive 8192-byte buffer to completely prevent underflow/crackling
try:
    pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=8192)
    pygame.mixer.init()
except Exception as e:
    print(f"[-] Pre-init failed: {e}. Falling back to standard init...")
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=8192)

# Initialize OLED
serial_i2c = i2c(port=1, address=0x3C)
display = sh1106(serial_i2c)

# Initialize NFC Reader (using direct serial0 path)
uart_device = serial.Serial("/dev/serial0", baudrate=115200, timeout=0.1)
pn532 = PN532_UART(uart_device, debug=False)
pn532.SAM_configuration()

# Initialize Buttons with hold times
vol_up_btn = Button(17, hold_time=1.5)
vol_down_btn = Button(27, hold_time=1.5)

# Initialize Bluetooth Manager
bt_manager = BluetoothManager()

# ==========================================
# 2. GLOBAL STATE TRACKING & METADATA
# ==========================================
volume = 5                  # Scaled 0 to 10
show_volume_until = 0       # Timestamp tracking overlay timeout
is_shutting_down = False

# State Management for Menus
STATE_PLAYING = 0
STATE_BT_MENU = 1
current_state = STATE_PLAYING

# BT Menu UI state
menu_index = 0
menu_message = ""
menu_message_timeout = 0

current_uid = None          # Tracks the physical presence of the tag
current_playing = False     # Tracks if music is actually flowing

# Cached current track details (audio, title, pre-rendered artwork image object)
current_title = ""
current_artwork_img = None  # Holds PIL.Image formatted specifically for SH1106
current_media_type = "audio" # "audio", "video", "radio", "slideshow"

# Active background processes (like VLC or mpv for internet radio streaming)
active_radio_process = None
radio_tune_start_time = 0.0   # Timestamp of when radio was triggered to show "tuning" state
current_station_freq = "96.7" # Default FM station frequency to display on retro UI

# Path configurations
CATALOG_PATH = "/opt/music-player/catalog.json"
LOCAL_CATALOG_FALLBACK = "catalog.json"

# Set initial audio volume (Pygame expects a float between 0.0 and 1.0)
pygame.mixer.music.set_volume(volume / 10.0)

# Slideshow State Variables
slideshow_images = []
slideshow_index = 0
next_slide_time = 0.0

def load_slideshow_images(folder_path):
    """Loads all image files from a folder and converts them to 1-bit monochrome."""
    images = []
    if not folder_path or not os.path.exists(folder_path):
        return images
    try:
        files = sorted(os.listdir(folder_path))
        for f in files:
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                full_path = os.path.join(folder_path, f)
                try:
                    img = Image.open(full_path)
                    if img.size != (128, 64):
                        img = img.resize((128, 64), Image.Resampling.NEAREST)
                    images.append(img.convert("1"))
                except Exception as e:
                    print(f"[-] Failed to load slideshow image {full_path}: {e}")
    except Exception as e:
        print(f"[-] Error loading slideshow folder {folder_path}: {e}")
    return images

# ==========================================
# 3. BUTTON CALLBACK FUNCTIONS
# ==========================================
def toggle_state():
    global current_state, menu_index, menu_message
    if is_shutting_down: return
    
    if current_state == STATE_PLAYING:
        current_state = STATE_BT_MENU
        menu_index = 0
        menu_message = "SCANNING..."
        bt_manager.start_scan()
        print("Switched to Bluetooth Menu State")
    else:
        current_state = STATE_PLAYING
        bt_manager.stop_scan()
        print("Switched to Playing State")

# Detect long chord press (both held)
def check_menu_toggle():
    if vol_up_btn.is_held and vol_down_btn.is_held:
        toggle_state()

vol_up_btn.when_held = check_menu_toggle
vol_down_btn.when_held = check_menu_toggle

def vol_up_pressed():
    global volume, show_volume_until, menu_index, current_state
    if is_shutting_down: return
    
    # If both are currently pressed down, skip individual actions
    if vol_down_btn.is_pressed:
        return
        
    if current_state == STATE_PLAYING:
        if volume < 10:
            volume += 1
            pygame.mixer.music.set_volume(volume / 10.0)
        show_volume_until = time.time() + 2.0
        print(f"Volume Up: {volume}/10")
    elif current_state == STATE_BT_MENU:
        # Move selector down the menu list
        devices = bt_manager.discovered_devices
        # +2 options: "Disconnect" and "Back"
        total_items = len(devices) + 2
        menu_index = (menu_index + 1) % total_items

def vol_down_pressed():
    global volume, show_volume_until, current_state, menu_index, menu_message, menu_message_timeout
    if is_shutting_down: return
    
    # If both are currently pressed down, skip individual actions
    if vol_up_btn.is_pressed:
        return

    if current_state == STATE_PLAYING:
        if volume > 0:
            volume -= 1
            pygame.mixer.music.set_volume(volume / 10.0)
        show_volume_until = time.time() + 2.0
        print(f"Volume Down: {volume}/10")
    elif current_state == STATE_BT_MENU:
        # SELECT highlight item
        devices = bt_manager.discovered_devices
        idx_disconnect = len(devices)
        idx_back = len(devices) + 1
        
        if menu_index < len(devices):
            # Connect to selected device
            selected = devices[menu_index]
            menu_message = "CONNECTING..."
            menu_message_timeout = time.time() + 10.0
            
            def conn_thread():
                global menu_message, menu_message_timeout
                success = bt_manager.connect_device(selected['mac'])
                if success:
                    menu_message = "CONNECTED!"
                else:
                    menu_message = "FAILED"
                menu_message_timeout = time.time() + 2.5
            
            threading.Thread(target=conn_thread, daemon=True).start()
            
        elif menu_index == idx_disconnect:
            if bt_manager.connected_device:
                mac = bt_manager.connected_device['mac']
                menu_message = "DISCONNECTING..."
                bt_manager.disconnect_device(mac)
                menu_message = "DISCONNECTED"
                menu_message_timeout = time.time() + 2.0
            else:
                menu_message = "NO DEVICE"
                menu_message_timeout = time.time() + 2.0
        elif menu_index == idx_back:
            toggle_state()

vol_up_btn.when_pressed = vol_up_pressed
vol_down_btn.when_pressed = vol_down_pressed

# ==========================================
# 4. NFC PARSING & CATALOG MATCHING LOGIC
# ==========================================
def load_catalog():
    """Loads metadata matching records from catalog.json."""
    paths_to_try = [CATALOG_PATH, LOCAL_CATALOG_FALLBACK]
    for path in paths_to_try:
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[-] Failed to load catalog from {path}: {e}")
    return {}

def extract_tag_payload():
    """
    Reads the raw blocks of the NTAG sticker and searches for:
    1. A song database ID key (e.g. "song_01", "song_02")
    2. A legacy Linux absolute file path ending in .mp3
    """
    raw_data = bytearray()
    try:
        for i in range(4, 20):
            block = pn532.ntag2xx_read_block(i)
            if block:
                raw_data.extend(block)
    except Exception as e:
        print("Read error:", e)
        return None

    # Decode bytes ignoring messy NDEF header characters
    text = raw_data.decode('ascii', errors='ignore')
    
    # Check catalog.json keys directly against raw text to bypass overlapping writes!
    catalog = load_catalog()
    for key in catalog.keys():
        if key in text:
            return key

    # Legacy regex lookup fallback for absolute paths
    match_path = re.search(r'(/home/.*?\.mp3)', text)
    if match_path:
        return match_path.group(1)
        
    return None

def resolve_playback_assets(payload):
    """
    Takes a tag payload and returns a dictionary with all metadata, including
    'audio', 'title', 'type', and 'artwork' (pre-rendered PIL image).
    """
    catalog = load_catalog()
    
    # Try database match
    if payload in catalog:
        entry = catalog[payload].copy()
        audio_path = entry.get("audio", "")
        title = entry.get("title", payload)
        image_path = entry.get("image", "")
        media_type = entry.get("type", "audio")
        
        # Load and pre-process artwork image
        artwork_img = None
        if image_path and os.path.exists(image_path):
            try:
                img = Image.open(image_path)
                # Resize to fit the exact OLED screen boundaries dynamically
                if img.size != (128, 64):
                    img = img.resize((128, 64), Image.Resampling.NEAREST)
                artwork_img = img.convert("1")
                print(f"[+] Loaded and processed artwork: {image_path}")
            except Exception as e:
                print(f"[-] Failed to process artwork image {image_path}: {e}")
                
        entry["audio"] = audio_path
        entry["title"] = title
        entry["type"] = media_type
        entry["artwork"] = artwork_img
        return entry
    
    # Legacy direct file path support
    if payload and payload.endswith(".mp3"):
        title = os.path.basename(payload).replace(".mp3", "").replace("_", " ").title()
        return {
            "type": "audio",
            "audio": payload,
            "title": title,
            "artwork": None
        }

    return None

# ==========================================
# 5. LUMA DRAWING UTILITIES
# ==========================================
def draw_bluetooth_icon(draw, x, y):
    """
    Draws a standard pixel-art Bluetooth logo at position x, y.
    Bounding box is roughly 7x11 pixels.
    """
    draw.line((x + 3, y, x + 3, y + 10), fill="white")
    draw.line((x + 3, y, x + 6, y + 3), fill="white")
    draw.line((x + 6, y + 3, x + 3, y + 5), fill="white")
    draw.line((x + 3, y + 5, x + 6, y + 7), fill="white")
    draw.line((x + 6, y + 7, x + 3, y + 10), fill="white")
    draw.line((x + 3, y + 2, x, y + 5), fill="white")
    draw.line((x, y + 5, x + 3, y + 8), fill="white")

def check_tag_removed():
    """Helper used by nested games/video loops to see if tag is removed."""
    uid = pn532.read_passive_target(timeout=0.05)
    return uid is None

def draw_music_screen(draw):
    global current_title, current_artwork_img, current_media_type, slideshow_images, slideshow_index, current_station_freq, frame_counter
    
    # Slideshow mode: draw current slide
    if current_media_type == "slideshow" and slideshow_images:
        draw.bitmap((0, 0), slideshow_images[slideshow_index], fill="white")
    # Custom artwork
    elif current_artwork_img is not None:
        draw.bitmap((0, 0), current_artwork_img, fill="white")
    # Radio Mode: Retro Tuner
    elif current_media_type == "radio":
        # Draw "FM TUNER" header
        draw.text((40, 2), "FM TUNER", fill="white")
        draw.line((0, 13, 128, 13), fill="white")
        
        # Check if we are in the initial 2.5 seconds "Tuning / Static search" phase
        tuning_duration = 2.5
        is_tuning = (time.time() - radio_tune_start_time) < tuning_duration
        
        if is_tuning:
            # Let's show search indicators
            # Animate frequency hunting randomly around target frequency
            try:
                target_freq = float(current_station_freq)
            except ValueError:
                target_freq = 96.7
            
            # Animate needle moving or sweeping towards target freq
            elapsed = time.time() - radio_tune_start_time
            progress = elapsed / tuning_duration # 0.0 to 1.0
            
            # Start sweep from 88.0 or from +5.0 MHz away, and oscillate
            start_sweep_freq = target_freq - 6.0
            if start_sweep_freq < 88.0:
                start_sweep_freq = 104.0
                
            sweep_freq = start_sweep_freq + (target_freq - start_sweep_freq) * progress
            # Add some rapid scanning jitter
            jitter = math.sin(time.time() * 50.0) * 0.4
            display_freq = sweep_freq + jitter
            
            freq_str = f"SEEK: {display_freq:.1f} MHz"
            draw.text((22, 18), freq_str, fill="white")
            
            # Render "TUNING..." blinking tag
            if frame_counter % 6 < 3:
                draw.text((40, 28), "TUNING...", fill="white")
            else:
                draw.text((40, 28), "[SIGNAL]", fill="white")
                
            # Render heavy static/noise at the bottom (random pixels/lines)
            import random
            for _ in range(30):
                rx = random.randint(10, 118)
                ry = random.randint(38, 48)
                draw.point((rx, ry), fill="white")
                
            # Map frequency to x coordinate 15-113
            normalized_freq = (display_freq - 88.0) / (108.0 - 88.0)
            normalized_freq = max(0.0, min(1.0, normalized_freq))
            needle_x = int(15 + normalized_freq * 98)
        else:
            # Display frequency locked
            freq_str = f"{current_station_freq} MHz"
            draw.text((36, 18), freq_str, fill="white")
            draw.text((44, 28), "[LOCKED]", fill="white")
            
            # Dial scale
            draw.line((10, 42, 118, 42), fill="white")
            for mark in range(10, 119, 12):
                draw.line((mark, 42, mark, 45), fill="white")
                
            # Tuner needle (animate slightly or center around the station)
            try:
                freq_num = float(current_station_freq)
            except ValueError:
                freq_num = 96.7
                
            # Map 88-108 MHz to x coordinate 15-113
            normalized_freq = (freq_num - 88.0) / (108.0 - 88.0)
            normalized_freq = max(0.0, min(1.0, normalized_freq))
            needle_x = int(15 + normalized_freq * 98)
            
            # Add a tiny visual wobble to look analog
            import random
            wobble = random.randint(-1, 1) if (frame_counter % 4 == 0) else 0
            needle_x += wobble
            needle_x = max(15, min(113, needle_x))
            
            draw.line((needle_x, 38, needle_x, 48), fill="white")
            draw.rectangle((needle_x - 1, 38, needle_x + 1, 40), fill="white")
            
            # Tiny retro signal strength indicator (3 vertical bars)
            draw.rectangle((108, 16, 110, 18), fill="white")
            draw.rectangle((112, 14, 114, 18), fill="white")
            draw.rectangle((116, 12, 118, 18), fill="white")
    else:
        # Scenario B: Render beautiful default player interface
        draw.text((34, 4), "NOW PLAYING", fill="white")
        title_text = current_title[:18] if current_title else "Cassette Mode"
        draw.text((30, 16), title_text, fill="white")
        
        # If VU visualizer enabled
        catalog = load_catalog()
        active_match = None
        for key, entry in catalog.items():
            if entry.get("title") == current_title:
                active_match = entry
                break
                
        if active_match and active_match.get("visualizer") == "vu_meter":
            # Draw beautiful VU Meter bars instead of cassette reels!
            import random
            bar_count = 10
            start_x = 14
            spacing = 10
            bar_width = 7
            for i in range(bar_count):
                # Generate dynamic level heights
                base_h = 5 + int(15 * (1.0 + abs(i - 4.5) / 5.0))
                # Add rapid fluctuation
                fluctuation = random.randint(-4, 4)
                h = max(2, min(24, base_h + fluctuation))
                
                bx1 = start_x + (i * spacing)
                by1 = 58 - h
                bx2 = bx1 + bar_width
                by2 = 58
                draw.rectangle((bx1, by1, bx2, by2), fill="white")
        else:
            # Retro Cassette Deck vectors
            draw.rectangle((36, 32, 92, 58), outline="white")
            draw.ellipse((48, 40, 58, 50), outline="white")
            draw.ellipse((70, 40, 80, 50), outline="white")
            draw.line((58, 45, 70, 45), fill="white")

    # Persistent Bluetooth indicator is layered over the artwork in the top-right corner
    if bt_manager.connected_device:
        draw_bluetooth_icon(draw, 115, 4)

def draw_volume_screen(draw, vol_level):
    draw.text((42, 4), "VOLUME", fill="white")
    start_x = 14
    spacing = 10
    width = 6
    for i in range(10):
        x1 = start_x + (i * spacing)
        y1 = 52 - (i * 2)
        x2 = x1 + width
        y2 = 54
        if i < vol_level:
            draw.rectangle((x1, y1, x2, y2), fill="white")
        else:
            draw.rectangle((x1, y2 - 2, x2, y2), fill="white")
    if bt_manager.connected_device:
        draw_bluetooth_icon(draw, 115, 4)

def draw_power_screen(draw):
    draw.text((44, 4), "SHUTDOWN", fill="white")
    draw.arc((48, 22, 80, 54), start=310, end=230, fill="white")
    draw.line((64, 16, 64, 34), fill="white")

def draw_waiting_screen(draw, pulse_frame):
    # Retrieve system time
    current_time_str = time.strftime("%H:%M:%S")
    current_date_str = time.strftime("%a, %b %d")

    # Draw top header bar
    draw.text((2, 2), current_date_str, fill="white")
    if bt_manager.connected_device:
        draw_bluetooth_icon(draw, 115, 2)
    draw.line((0, 13, 128, 13), fill="white")

    # Draw massive, beautiful analog-style digital clock in center
    # Uses coordinates to space out characters nicely on the monochrome screen
    draw.text((32, 20), current_time_str, fill="white")

    # Animated retro status indicator at bottom
    # We show "STANDBY" and a slow, beautiful breathing pulsing visual line
    draw.text((12, 42), "INSERT TOKEN", fill="white")
    
    # Breathing pulse dot line mapping to frame counter
    pulse_width = int(6 + 6 * math.sin(pulse_frame * 0.2)) # Breathing animation
    draw.rectangle((94, 46, 94 + pulse_width, 48), fill="white")

def draw_bt_menu_screen(draw):
    draw.text((4, 2), "BLUETOOTH MENU", fill="white")
    draw.line((0, 13, 128, 13), fill="white")
    
    if bt_manager.connected_device:
        draw_bluetooth_icon(draw, 115, 2)
        
    global menu_message, menu_message_timeout
    if menu_message and time.time() < menu_message_timeout:
        draw.text((20, 32), menu_message, fill="white")
        return

    devices = bt_manager.discovered_devices
    idx_disconnect = len(devices)
    idx_back = len(devices) + 1

    start_offset = 0
    if menu_index >= 3:
        start_offset = menu_index - 2

    for line_idx in range(3):
        item_idx = start_offset + line_idx
        y_pos = 18 + (line_idx * 15)
        cursor = ">" if item_idx == menu_index else " "
        
        if item_idx < len(devices):
            dev = devices[item_idx]
            name = dev['name'][:16]
            draw.text((4, y_pos), f"{cursor} {name}", fill="white")
        elif item_idx == idx_disconnect:
            connected = bt_manager.connected_device
            disp_text = f"Disconnect ({connected['name'][:8]})" if connected else "Disconnect"
            draw.text((4, y_pos), f"{cursor} {disp_text}", fill="white")
        elif item_idx == idx_back:
            draw.text((4, y_pos), f"{cursor} [Back to Player]", fill="white")

# Performance tracking and loop states
frame_counter = 0

# ==========================================
# 6. MAIN EXECUTION ENGINE
# ==========================================
def main():
    global volume, show_volume_until, is_shutting_down, current_uid, current_playing, current_state
    global current_title, current_artwork_img, current_media_type, slideshow_images, slideshow_index, next_slide_time, active_radio_process, current_station_freq, frame_counter
    
    print("Analog Music Player Active! Waiting for tag...")
    frame_counter = 0

    # Clean systemd stop handling using signals
    def signal_handler(sig, frame):
        global is_shutting_down
        print("\n[+] Shutdown signal received. Stopping music-player service gracefully...")
        is_shutting_down = True

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        while True:
            with canvas(display) as draw:
                
                # Priority 1: Shutdown
                if is_shutting_down:
                    pygame.mixer.music.stop()
                    draw_power_screen(draw)
                    bt_manager.stop_monitors()
                    time.sleep(2.0)
                    break
                    
                # Priority 2: Bluetooth Menu Mode
                elif current_state == STATE_BT_MENU:
                    draw_bt_menu_screen(draw)
                    
                # Priority 3: Volume Overlay
                elif time.time() < show_volume_until:
                    draw_volume_screen(draw, volume)
                    
                # Priority 4: Normal Playback Logic
                else:
                    # Fast presence check
                    uid = pn532.read_passive_target(timeout=0.05)
                    
                    if uid is not None:
                        # Is this a newly placed tag?
                        if current_uid != uid.hex():
                            current_uid = uid.hex()
                            print("New tag detected! Reading payload...")
                            
                            # Reset states before matching new tag
                            if active_radio_process:
                                active_radio_process.terminate()
                                active_radio_process.wait()
                                active_radio_process = None
                            pygame.mixer.music.stop()
                            
                            payload = extract_tag_payload()
                            print(f"Decoded Tag Payload: {payload}")
                            
                            assets = resolve_playback_assets(payload) if payload else None
                            
                            if assets:
                                current_media_type = assets.get("type", "audio")
                                current_title = assets.get("title", "Untitled")
                                current_artwork_img = assets.get("artwork", None)
                                
                                # 1. GAME MODULE TRIGGER
                                if current_media_type == "game":
                                    print(f"Loading Game: {current_title}")
                                    # This completely intercepts control until tag is removed!
                                    run_snake_game(display, pn532, vol_up_btn, vol_down_btn, check_tag_removed)
                                    # Once game exits, clear tag presence to avoid instant re-trigger
                                    current_uid = None
                                    current_playing = False
                                    continue
                                
                                # 2. VIDEO MODULE TRIGGER
                                elif current_media_type == "video":
                                    video_file = assets.get("video")
                                    audio_file = assets.get("audio") # Get audio file defined in catalog.json!
                                    print(f"Loading Video: {current_title} ({video_file}) -> audio: {audio_file}")
                                    if video_file and os.path.exists(video_file):
                                        # Intercept display loop and play video frames sequentially
                                        play_preprocessed_bin(
                                            video_file,
                                            display=display,
                                            check_tag_removed_fn=check_tag_removed,
                                            vol_up_btn=vol_up_btn,
                                            vol_down_btn=vol_down_btn,
                                            get_volume_fn=lambda: volume,
                                            set_volume_fn=lambda v: globals().update(volume=v),
                                            audio_path=audio_file # Pass the catalog.json audio path!
                                        )
                                    else:
                                        print("Video file not found!")
                                    # Clear tag presence once video player exits
                                    current_uid = None
                                    current_playing = False
                                    continue
                                    
                                # 3. RADIO STREAM TRIGGER
                                elif current_media_type == "radio":
                                    stream_url = assets.get("stream_url", "")
                                    current_station_freq = assets.get("station_freq", "96.7")
                                    radio_tune_start_time = time.time() # Mark start of retro search sweep!
                                    print(f"Streaming radio: {current_title} ({stream_url})")
                                    if stream_url:
                                        try:
                                            # Launch headless command line player for internet radio streams
                                            # (mpv, cvlc, etc.)
                                            active_radio_process = subprocess.Popen(
                                                ["mpv", "--no-video", stream_url],
                                                stdout=subprocess.DEVNULL,
                                                stderr=subprocess.DEVNULL
                                            )
                                            current_playing = True
                                        except Exception as e:
                                            print(f"[-] Failed to launch radio process: {e}")
                                            current_playing = False
                                    else:
                                        current_playing = False
                                        
                                # 4. PHOTO SLIDESHOW TRIGGER
                                elif current_media_type == "slideshow":
                                    folder_path = assets.get("folder", "")
                                    audio_path = assets.get("audio", "")
                                    interval = float(assets.get("interval", 5.0))
                                    print(f"Slideshow active: {current_title} ({folder_path})")
                                    
                                    # Load images from directory
                                    slideshow_images = load_slideshow_images(folder_path)
                                    slideshow_index = 0
                                    next_slide_time = time.time() + interval
                                    
                                    if audio_path and os.path.exists(audio_path):
                                        pygame.mixer.music.load(audio_path)
                                        pygame.mixer.music.play(-1) # Loop forever
                                        
                                    current_playing = True
                                    
                                # 5. STANDARD AUDIO PLAYBACK
                                else:
                                    file_path = assets.get("audio", "")
                                    if file_path and os.path.exists(file_path):
                                        print(f"Playing: {current_title} ({file_path})")
                                        pygame.mixer.music.load(file_path)
                                        pygame.mixer.music.play()
                                        current_playing = True
                                    else:
                                        print("Audio file not found on device.")
                                        current_playing = False
                            else:
                                print("Invalid tag payload.")
                                current_playing = False
                                current_title = ""
                                current_artwork_img = None
                        
                        # Tag is physically on the scanner (Continuous update logic)
                        if current_playing:
                            # Handle slideshow index rotation
                            if current_media_type == "slideshow" and slideshow_images:
                                if time.time() >= next_slide_time:
                                    slideshow_index = (slideshow_index + 1) % len(slideshow_images)
                                    # Fetch current interval from metadata fallback
                                    assets = resolve_playback_assets(payload)
                                    interval = float(assets.get("interval", 5.0)) if assets else 5.0
                                    next_slide_time = time.time() + interval
                            
                            draw_music_screen(draw)
                        else:
                            draw.text((20, 28), "FILE NOT FOUND", fill="white")
                            
                    else:
                        # Platter is empty
                        if current_uid is not None:
                            # Tag was just removed
                            print("Tag removed. Halting audio.")
                            if active_radio_process:
                                active_radio_process.terminate()
                                active_radio_process.wait()
                                active_radio_process = None
                            pygame.mixer.music.stop()
                            current_uid = None
                            current_playing = False
                            current_title = ""
                            current_artwork_img = None
                            current_media_type = "audio"
                            slideshow_images = []
                            
                        draw_waiting_screen(draw, frame_counter)
                        
            frame_counter += 1
            # Reduced sleep time to 0.05s and split it to check is_shutting_down quicker
            for _ in range(5):
                if is_shutting_down:
                    break
                time.sleep(0.02)

    except KeyboardInterrupt:
        print("\nPlayer stopped cleanly.")
    finally:
        if active_radio_process:
            try:
                active_radio_process.terminate()
                active_radio_process.wait()
            except Exception:
                pass
        pygame.mixer.music.stop()
        bt_manager.stop_monitors()
        # Ensure pygame is completely shutdown to release sound device immediately
        pygame.mixer.quit()
        pygame.quit()
        print("[+] Player resource cleanup finished.")
        sys.exit(0)

if __name__ == "__main__":
    main()
