from music_player.ui.screens.base_screen import BaseScreen
from music_player.ui.assets import draw_bluetooth_icon


class VolumeScreen(BaseScreen):
    """Displays current volume level as a 10-bar vertical meter."""
    
    def draw(self, draw, state, bt_manager):
        draw.text((42, 4), "VOLUME", fill="white")
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
