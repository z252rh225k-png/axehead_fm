from music_player.ui.screens.base_screen import BaseScreen


class PowerScreen(BaseScreen):
    """Displays shutdown confirmation screen."""
    
    def draw(self, draw, state, bt_manager):
        draw.text((44, 4), "SHUTDOWN", fill="white")
        draw.arc((48, 22, 80, 54), start=310, end=230, fill="white")
        draw.line((64, 16, 64, 34), fill="white")
