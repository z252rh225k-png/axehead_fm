import time
import math
import random
from PIL import ImageFont
from music_player.ui.assets import draw_bluetooth_icon
from music_player.catalog.loader import load_catalog

# Preload fonts for best rendering performance
try:
    font_small = ImageFont.truetype("fonts/Nintendo-DS-BIOS.ttf", 12)
    font_large = ImageFont.truetype("fonts/Nintendo-DS-BIOS.ttf", 16)
except Exception:
    # Fallback to default if font file is missing
    font_small = None
    font_large = None

class BaseScreen:
    def draw(self, draw, state, bt_manager):
        pass


class MusicScreen(BaseScreen):
    def draw(self, draw, state, bt_manager, spectrum_analyzer=None, beat_detector=None):
        # Slideshow mode: draw current slide
        if state.current_media_type == "slideshow" and state.slideshow_images:
            draw.bitmap((0, 0), state.slideshow_images[state.slideshow_index], fill="white")
        # Audio playback mode: Show spectrum visualization
        elif state.current_media_type == "audio":
            draw.text((34, 4), "NOW PLAYING", fill="white", font=font_small)
            title_text = state.current_title[:18] if state.current_title else "Cassette Mode"
            draw.text((30, 16), title_text, fill="white", font=font_small)
            
            # Draw spectrum analyzer bars if available
            if spectrum_analyzer:
                spectrum = spectrum_analyzer.get_spectrum()
                if spectrum is not None and len(spectrum) > 0:
                    # Draw 16 spectrum bands
                    bar_count = min(16, len(spectrum))
                    start_x = 4
                    spacing = 7
                    bar_width = 6
                    max_height = 28
                    
                    for i in range(bar_count):
                        magnitude = spectrum[i]
                        h = int(magnitude * max_height)
                        h = max(1, min(max_height, h))
                        
                        bx1 = start_x + (i * spacing)
                        by1 = 58 - h
                        bx2 = bx1 + bar_width
                        by2 = 58
                        draw.rectangle((bx1, by1, bx2, by2), fill="white")
                else:
                    # Fallback: Retro Cassette Deck vectors
                    draw.rectangle((36, 32, 92, 58), outline="white")
                    draw.ellipse((48, 40, 58, 50), outline="white")
                    draw.ellipse((70, 40, 80, 50), outline="white")
                    draw.line((58, 45, 70, 45), fill="white")
            else:
                # Fallback: Retro Cassette Deck vectors
                draw.rectangle((36, 32, 92, 58), outline="white")
                draw.ellipse((48, 40, 58, 50), outline="white")
                draw.ellipse((70, 40, 80, 50), outline="white")
                draw.line((58, 45, 70, 45), fill="white")
        # Custom artwork (video, image modes, etc)
        elif state.current_artwork_img is not None:
            draw.bitmap((0, 0), state.current_artwork_img, fill="white")
        # Radio Mode: Retro Tuner
        elif state.current_media_type == "radio":
            draw.text((40, 2), "FM TUNER", fill="white", font=font_small)
            draw.line((0, 13, 128, 13), fill="white")
            
            tuning_duration = 2.5
            is_tuning = (time.time() - state.radio_tune_start_time) < tuning_duration
            
            if is_tuning:
                try:
                    target_freq = float(state.current_station_freq)
                except ValueError:
                    target_freq = 96.7
                
                elapsed = time.time() - state.radio_tune_start_time
                progress = elapsed / tuning_duration
                
                start_sweep_freq = target_freq - 6.0
                if start_sweep_freq < 88.0:
                    start_sweep_freq = 104.0
                    
                sweep_freq = start_sweep_freq + (target_freq - start_sweep_freq) * progress
                jitter = math.sin(time.time() * 50.0) * 0.4
                display_freq = sweep_freq + jitter
                
                freq_str = f"SEEK: {display_freq:.1f} MHz"
                draw.text((22, 18), freq_str, fill="white", font=font_small)
                
                if state.frame_counter % 6 < 3:
                    draw.text((40, 28), "TUNING...", fill="white", font=font_small)
                else:
                    draw.text((40, 28), "[SIGNAL]", fill="white", font=font_small)
                    
                for _ in range(30):
                    rx = random.randint(10, 118)
                    ry = random.randint(38, 48)
                    draw.point((rx, ry), fill="white")
                    
                normalized_freq = (display_freq - 88.0) / (108.0 - 88.0)
                normalized_freq = max(0.0, min(1.0, normalized_freq))
                needle_x = int(15 + normalized_freq * 98)
            else:
                freq_str = f"{state.current_station_freq} MHz"
                draw.text((36, 18), freq_str, fill="white", font=font_small)
                draw.text((44, 28), "[LOCKED]", fill="white", font=font_small)
                
                draw.line((10, 42, 118, 42), fill="white")
                for mark in range(10, 119, 12):
                    draw.line((mark, 42, mark, 45), fill="white")
                    
                try:
                    freq_num = float(state.current_station_freq)
                except ValueError:
                    freq_num = 96.7
                    
                normalized_freq = (freq_num - 88.0) / (108.0 - 88.0)
                normalized_freq = max(0.0, min(1.0, normalized_freq))
                needle_x = int(15 + normalized_freq * 98)
                
                wobble = random.randint(-1, 1) if (state.frame_counter % 4 == 0) else 0
                needle_x += wobble
                needle_x = max(15, min(113, needle_x))
                
                draw.line((needle_x, 38, needle_x, 48), fill="white")
                draw.rectangle((needle_x - 1, 38, needle_x + 1, 40), fill="white")
                
                draw.rectangle((108, 16, 110, 18), fill="white")
                draw.rectangle((112, 14, 114, 18), fill="white")
                draw.rectangle((116, 12, 118, 18), fill="white")
        else:
            # Scenario B: Render beautiful default player interface
            draw.text((34, 4), "NOW PLAYING", fill="white", font=font_small)
            title_text = state.current_title[:18] if state.current_title else "Cassette Mode"
            draw.text((30, 16), title_text, fill="white", font=font_small)
            
            # If VU visualizer enabled
            catalog = load_catalog()
            active_match = None
            for key, entry in catalog.items():
                if entry.get("title") == state.current_title:
                    active_match = entry
                    break
                    
            if active_match and active_match.get("visualizer") == "vu_meter":
                bar_count = 10
                start_x = 14
                spacing = 10
                bar_width = 7
                for i in range(bar_count):
                    base_h = 5 + int(15 * (1.0 + abs(i - 4.5) / 5.0))
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

        if bt_manager.connected_device:
            draw_bluetooth_icon(draw, 115, 4)


class VolumeScreen(BaseScreen):
    def draw(self, draw, state, bt_manager, spectrum_analyzer=None, beat_detector=None):
        draw.text((42, 4), "VOLUME", fill="white", font=font_small)
        start_x = 14
        spacing = 10
        width = 6
        for i in range(10):
            x1 = start_x + (i * spacing)
            y1 = 52 - (i * 2)
            x2 = x1 + width
            y2 = 54
            if i < state.volume:
                draw.rectangle((x1, y1, x2, y2), fill="white")
            else:
                draw.rectangle((x1, y2 - 2, x2, y2), fill="white")
        if bt_manager.connected_device:
            draw_bluetooth_icon(draw, 115, 4)


class PowerScreen(BaseScreen):
    def draw(self, draw, state, bt_manager, spectrum_analyzer=None, beat_detector=None):
        draw.text((44, 4), "SHUTDOWN", fill="white", font=font_small)
        draw.arc((48, 22, 80, 54), start=310, end=230, fill="white")
        draw.line((64, 16, 64, 34), fill="white")


class WaitingScreen(BaseScreen):
    def draw(self, draw, state, bt_manager, spectrum_analyzer=None, beat_detector=None):
        current_time_str = time.strftime("%H:%M:%S")
        current_date_str = time.strftime("%a, %b %d")

        draw.text((2, 2), current_date_str, fill="white", font=font_small)
        if bt_manager.connected_device:
            draw_bluetooth_icon(draw, 115, 2)
        draw.line((0, 13, 128, 13), fill="white")

        draw.text((32, 20), current_time_str, fill="white", font=font_large)

        draw.text((12, 42), "INSERT TOKEN", fill="white", font=font_large)
        
        pulse_width = int(6 + 6 * math.sin(state.frame_counter * 0.2))
        draw.rectangle((94, 46, 94 + pulse_width, 48), fill="white")


class BTMenuScreen(BaseScreen):
    def draw(self, draw, state, bt_manager, spectrum_analyzer=None, beat_detector=None):
        draw.text((4, 2), "BLUETOOTH MENU", fill="white", font=font_small)
        draw.line((0, 13, 128, 13), fill="white")
        
        if bt_manager.connected_device:
            draw_bluetooth_icon(draw, 115, 2)
            
        if state.menu_message and time.time() < state.menu_message_timeout:
            draw.text((20, 32), state.menu_message, fill="white", font=font_small)
            return

        devices = bt_manager.discovered_devices
        idx_disconnect = len(devices)
        idx_back = len(devices) + 1

        start_offset = 0
        if state.menu_index >= 3:
            start_offset = state.menu_index - 2

        for line_idx in range(3):
            item_idx = start_offset + line_idx
            y_pos = 18 + (line_idx * 15)
            cursor = ">" if item_idx == state.menu_index else " "
            
            if item_idx < len(devices):
                dev = devices[item_idx]
                name = dev['name'][:16]
                draw.text((4, y_pos), f"{cursor} {name}", fill="white", font=font_small)
            elif item_idx == idx_disconnect:
                connected = bt_manager.connected_device
                disp_text = f"Disconnect ({connected['name'][:8]})" if connected else "Disconnect"
                draw.text((4, y_pos), f"{cursor} {disp_text}", fill="white", font=font_small)
            elif item_idx == idx_back:
                draw.text((4, y_pos), f"{cursor} [Back to Player]", fill="white", font=font_small)
