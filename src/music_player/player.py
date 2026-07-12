import time
import sys
import threading
import signal
import logging
import os
from pathlib import Path
from music_player.hardware.nfc_reader import NFCReader, is_wifi_tag, parse_wifi_ndef
from music_player.hardware.display import Display
from music_player.hardware.audio_engine import AudioEngine
from music_player.hardware.button_controller import ButtonController
from music_player.bluetooth_manager import BluetoothManager
from music_player.hardware.network_manager import get_network_manager
from music_player.hardware.init_utils import start_audio_detection_thread
from music_player.state.player_state import PlayerState
from music_player.catalog.resolver import extract_tag_payload, resolve_playback_assets
from music_player.ui.renderer import UIRenderer

# Handlers
from music_player.handlers.audio_handler import AudioHandler
from music_player.handlers.video_handler import VideoHandler
from music_player.handlers.radio_handler import RadioHandler
from music_player.handlers.slideshow_handler import SlideshowHandler
from music_player.handlers.game_handler import GameHandler
from music_player.handlers.qr_handler import QRHandler
from music_player.handlers.pokedex_handler import PokedexHandler

class MusicPlayer:
    def __init__(self):
        # 1. State
        self.state = PlayerState()

        # 2. Hardware
        self.nfc_reader = NFCReader()
        self.display = Display()
        self.audio_engine = AudioEngine()
        self.bt_manager = BluetoothManager()
        
        self.hardware_dict = {
            "nfc_reader": self.nfc_reader,
            "display": self.display,
            "audio_engine": self.audio_engine,
            "bt_manager": self.bt_manager
        }

        self.button_controller = ButtonController(
            toggle_callback=self.toggle_bt_state,
            vol_up_callback=self.volume_up,
            vol_down_callback=self.volume_down
        )
        self.hardware_dict["button_controller"] = self.button_controller
        self.network_manager = get_network_manager()

        # 3. Handlers
        self.handlers = {
            "audio": AudioHandler(),
            "video": VideoHandler(),
            "radio": RadioHandler(),
            "slideshow": SlideshowHandler(),
            "game": GameHandler(),
            "qr": QRHandler(),
            "pokedex": PokedexHandler()
        }
        self.current_active_handler = None

        # 4. UI Renderer
        self.ui_renderer = UIRenderer()

    def toggle_bt_state(self):
        if self.state.is_shutting_down:
            return
        
        if self.state.current_state == 0: # STATE_PLAYING
            self.state.current_state = 1 # STATE_BT_MENU
            self.state.menu_index = 0
            self.state.menu_message = "SCANNING..."
            self.bt_manager.start_scan()
            print("Switched to Bluetooth Menu State")
        else:
            self.state.current_state = 0 # STATE_PLAYING
            self.bt_manager.stop_scan()
            print("Switched to Playing State")

    def volume_up(self):
        if self.state.is_shutting_down:
            return
            
        if self.state.current_state == 0: # STATE_PLAYING
            self.state.set_volume(self.state.volume + 1)
            print(f"Volume Up: {self.state.volume}/10")
        elif self.state.current_state == 1: # STATE_BT_MENU
            devices = self.bt_manager.discovered_devices
            total_items = len(devices) + 2 # +2 for "Disconnect" and "Back"
            self.state.menu_index = (self.state.menu_index + 1) % total_items

    def volume_down(self):
        if self.state.is_shutting_down:
            return

        if self.state.current_state == 0: # STATE_PLAYING
            self.state.set_volume(self.state.volume - 1)
            print(f"Volume Down: {self.state.volume}/10")
        elif self.state.current_state == 1: # STATE_BT_MENU
            devices = self.bt_manager.discovered_devices
            idx_disconnect = len(devices)
            idx_back = len(devices) + 1
            
            if self.state.menu_index < len(devices):
                # Connect to selected device
                selected = devices[self.state.menu_index]
                self.state.menu_message = "CONNECTING..."
                self.state.menu_message_timeout = time.time() + 10.0
                
                def conn_thread():
                    success = self.bt_manager.connect_device(selected['mac'])
                    if success:
                        self.state.menu_message = "CONNECTED!"
                    else:
                        self.state.menu_message = "FAILED"
                    self.state.menu_message_timeout = time.time() + 2.5
                
                threading.Thread(target=conn_thread, daemon=True).start()
                
            elif self.state.menu_index == idx_disconnect:
                if self.bt_manager.connected_device:
                    mac = self.bt_manager.connected_device['mac']
                    self.state.menu_message = "DISCONNECTING..."
                    self.bt_manager.disconnect_device(mac)
                    self.state.menu_message = "DISCONNECTED"
                    self.state.menu_message_timeout = time.time() + 2.0
                else:
                    self.state.menu_message = "NO DEVICE"
                    self.state.menu_message_timeout = time.time() + 2.0
            elif self.state.menu_index == idx_back:
                self.toggle_bt_state()

    def handle_shutdown(self):
        print("\n[+] Shutdown signal received. Stopping music-player service gracefully...")
        self.state.is_shutting_down = True

    def run(self):
        print("Analog Music Player Active! Waiting for tag...")
        self.state.frame_counter = 0

        # Register signals
        signal.signal(signal.SIGINT, lambda sig, frame: self.handle_shutdown())
        signal.signal(signal.SIGTERM, lambda sig, frame: self.handle_shutdown())

        try:
            while True:
                # 1. UI Rendering
                self.ui_renderer.render(self.display, self.state, self.bt_manager)

                # 2. Priority 1: Shutdown handling
                if self.state.is_shutting_down:
                    self.audio_engine.stop()
                    self.ui_renderer.render(self.display, self.state, self.bt_manager)
                    self.bt_manager.stop_monitors()
                    time.sleep(2.0)
                    break

                # 3. Priority 2: Bluetooth Menu Mode (no tag logic should interrupt)
                elif self.state.current_state == 1: # STATE_BT_MENU
                    pass

                # 4. Priority 3: Volume Overlay active
                elif time.time() < self.state.show_volume_until:
                    pass

                # 5. Priority 4: Normal Playback Logic
                else:
                    uid = self.nfc_reader.read_passive_target(timeout=0.05)
                    
                    if uid is not None:
                        # New tag detected
                        if self.state.current_uid != uid.hex():
                            self.state.current_uid = uid.hex()
                            print("New tag detected! Reading payload...")
                            
                            # Clean up active handler
                            if self.current_active_handler:
                                self.current_active_handler.stop(self.state, self.hardware_dict)
                                self.current_active_handler = None
                            
                            payload = extract_tag_payload(self.nfc_reader)
                            wifi_payload = self.nfc_reader.read_wifi_payload(timeout=0.05) if hasattr(self.nfc_reader, "read_wifi_payload") else None
                            if wifi_payload and is_wifi_tag(self.state.current_uid, wifi_payload):
                                credentials = parse_wifi_ndef(wifi_payload)
                                if credentials:
                                    success, message = self.network_manager.connect_wifi(
                                        credentials.get("ssid", ""),
                                        credentials.get("password", ""),
                                        credentials.get("security", "WPA2"),
                                    )
                                    print(f"Wi-Fi provisioning result: {message}")
                                    self.state.current_title = "WiFi Setup"
                                    self.state.current_media_type = "wifi"
                                    self.state.current_playing = False
                                    self.state.current_artwork_img = None
                                    self.state.menu_message = message
                                    self.state.menu_message_timeout = time.time() + 4.0
                                payload = None
                            print(f"Decoded Tag Payload: {payload}")
                            
                            assets = resolve_playback_assets(payload) if payload else None
                            
                            if assets:
                                self.state.current_media_type = assets.get("type", "audio")
                                self.state.current_title = assets.get("title", "Untitled")
                                self.state.current_artwork_img = assets.get("artwork", None)
                                
                                handler_type = self.state.current_media_type
                                if handler_type in self.handlers:
                                    self.current_active_handler = self.handlers[handler_type]
                                    self.current_active_handler.play(assets, self.state, self.hardware_dict)
                                else:
                                    print(f"[-] No handler registered for media type: {handler_type}")
                                    self.state.current_playing = False
                            else:
                                print("Invalid tag payload.")
                                self.state.current_playing = False
                                self.state.current_title = ""
                                self.state.current_artwork_img = None

                        # Tag is present, run updates if any
                        if self.current_active_handler:
                            self.current_active_handler.update(self.state, self.hardware_dict)

                    else:
                        # Platter is empty (Tag removed)
                        if self.state.current_uid is not None:
                            print("Tag removed. Starting fade out.")
                            if self.current_active_handler:
                                # Initiate fade out
                                self.current_active_handler.stop(self.state, self.hardware_dict)
                            self.state.current_uid = None
                        
                        # Continue calling update while fade out completes
                        if self.current_active_handler:
                            self.current_active_handler.update(self.state, self.hardware_dict)
                        
                        # Cleanup when audio is no longer playing and no tag
                        if not self.state.current_playing and self.state.current_uid is None:
                            if self.current_active_handler:
                                self.current_active_handler = None
                            self.state.current_title = ""
                            self.state.current_artwork_img = None
                            self.state.current_media_type = "audio"
                            self.state.slideshow_images = []

                self.state.frame_counter += 1
                for _ in range(5):
                    if self.state.is_shutting_down:
                        break
                    time.sleep(0.02)

        except KeyboardInterrupt:
            print("\nPlayer stopped cleanly.")
        finally:
            self.cleanup()

    def cleanup(self):
        if self.current_active_handler:
            self.current_active_handler.stop(self.state, self.hardware_dict)
        self.bt_manager.stop_monitors()
        self.audio_engine.quit()
        print("[+] Player resource cleanup finished.")
        sys.exit(0)


def setup_logging():
    """Configure logging to file and console."""
    log_dir = Path('/opt/music-player/logs')
    
    # Try to create/fix log directory permissions
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        # Try to fix permissions if we can (in case ansible didn't set them right)
        log_dir.chmod(0o755)
    except Exception as e:
        print(f"[!] Warning: Could not ensure log directory: {e}", file=sys.stderr)
    
    log_file = log_dir / 'music-player.log'
    
    # Create logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    
    # Try to create file handler, fall back to console-only if it fails
    file_handler = None
    try:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    except PermissionError as e:
        print(f"[!] Warning: Cannot write to {log_file}: {e}", file=sys.stderr)
        print(f"[!] Falling back to console-only logging", file=sys.stderr)
    except Exception as e:
        print(f"[!] Warning: Error setting up file logging: {e}", file=sys.stderr)
    
    # Console handler - write info and above
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    return logging.getLogger(__name__)


def main():
    # Setup logging first
    logger = setup_logging()
    logger.info("🎵 Starting Axehead FM Music Player...")
    
    # Initialize Pokédex cache (pre-cache Gen 1 Pokémon)
    try:
        from music_player.pokedex_cache import setup_cache
        logger.info("Initializing Pokédex cache...")
        setup_cache()
        logger.info("Pokédex cache ready!")
    except ImportError:
        logger.warning("Pokédex module not available, skipping cache setup")
    except Exception as e:
        logger.warning(f"Pokédex cache setup error (non-fatal): {e}")
    
    # Start USB audio hardware detection in background thread (non-blocking)
    # This allows the player to start immediately while waiting for USB audio to appear
    logger.info("Starting audio hardware detection (background thread)...")
    start_audio_detection_thread(callback=None, timeout=30)
    
    # Initialize and run player immediately (don't wait for audio hardware)
    logger.info("Initializing player services...")
    player = MusicPlayer()
    player.run()

if __name__ == "__main__":
    main()
