import time
import random
from music_player.ui.screens.base_screen import BaseScreen
from music_player.ui.assets import draw_bluetooth_icon
from music_player.catalog.loader import load_catalog


class MusicScreen(BaseScreen):
    def draw(self, draw, state, bt_manager):
        # Slideshow mode: draw current slide
        if state.current_media_type == "slideshow" and state.slideshow_images:
            draw.bitmap((0, 0), state.slideshow_images[state.slideshow_index], fill="white")
        # Custom artwork
        elif state.current_artwork_img is not None:
            draw.bitmap((0, 0), state.current_artwork_img, fill="white")
        # Radio Mode: Retro Tuner
        elif state.current_media_type == "radio":
            self._draw_radio_tuner(draw, state)
        else:
            # Default audio player interface
            self._draw_audio_player(draw, state)

        if bt_manager.connected_device:
            draw_bluetooth_icon(draw, 115, 4)

    def _draw_radio_tuner(self, draw, state):
        """Draw the FM radio tuner screen."""
        import math
        
        draw.text((40, 2), "FM TUNER", fill="white")
        draw.line((0, 13, 128, 13), fill="white")
        
        tuning_duration = 2.5
        is_tuning = (time.time() - state.radio_tune_start_time) < tuning_duration
        
        if is_tuning:
            self._draw_tuning_animation(draw, state, tuning_duration)
        else:
            self._draw_locked_tuner(draw, state)

    def _draw_tuning_animation(self, draw, state, tuning_duration):
        """Draw the animated tuning state."""
        import math
        
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
        draw.text((22, 18), freq_str, fill="white")
        
        if state.frame_counter % 6 < 3:
            draw.text((40, 28), "TUNING...", fill="white")
        else:
            draw.text((40, 28), "[SIGNAL]", fill="white")
            
        for _ in range(30):
            rx = random.randint(10, 118)
            ry = random.randint(38, 48)
            draw.point((rx, ry), fill="white")
            
        normalized_freq = (display_freq - 88.0) / (108.0 - 88.0)
        normalized_freq = max(0.0, min(1.0, normalized_freq))
        needle_x = int(15 + normalized_freq * 98)

    def _draw_locked_tuner(self, draw, state):
        """Draw the locked (not tuning) radio state."""
        freq_str = f"{state.current_station_freq} MHz"
        draw.text((36, 18), freq_str, fill="white")
        draw.text((44, 28), "[LOCKED]", fill="white")
        
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

    def _draw_audio_player(self, draw, state):
        """Draw the default audio player interface."""
        draw.text((34, 4), "NOW PLAYING", fill="white")
        title_text = state.current_title[:18] if state.current_title else "Cassette Mode"
        draw.text((30, 16), title_text, fill="white")
        
        # Check if VU meter visualizer is enabled
        catalog = load_catalog()
        active_match = None
        for key, entry in catalog.items():
            if entry.get("title") == state.current_title:
                active_match = entry
                break
                
        if active_match and active_match.get("visualizer") == "vu_meter":
            self._draw_vu_meter(draw, state)
        else:
            self._draw_cassette_deck(draw)

    def _draw_vu_meter(self, draw, state):
        """Draw the VU meter visualizer."""
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

    def _draw_cassette_deck(self, draw):
        """Draw the retro cassette deck graphic."""
        draw.rectangle((36, 32, 92, 58), outline="white")
        draw.ellipse((48, 40, 58, 50), outline="white")
        draw.ellipse((70, 40, 80, 50), outline="white")
        draw.line((58, 45, 70, 45), fill="white")
