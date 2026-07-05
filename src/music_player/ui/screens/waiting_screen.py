import time
import math
from music_player.ui.screens.base_screen import BaseScreen
from music_player.ui.assets import draw_bluetooth_icon


class WaitingScreen(BaseScreen):
    """Displays idle/waiting screen with clock and NFC prompt."""
    
    def draw(self, draw, state, bt_manager):
        current_time_str = time.strftime("%H:%M:%S")
        current_date_str = time.strftime("%a, %b %d")

        draw.text((2, 2), current_date_str, fill="white")
        if bt_manager.connected_device:
            draw_bluetooth_icon(draw, 115, 2)
        draw.line((0, 13, 128, 13), fill="white")

        draw.text((32, 20), current_time_str, fill="white")

        draw.text((12, 42), "INSERT TOKEN", fill="white")
        
        # Pulsing indicator
        pulse_width = int(6 + 6 * math.sin(state.frame_counter * 0.2))
        draw.rectangle((94, 46, 94 + pulse_width, 48), fill="white")
