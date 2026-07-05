import time
from music_player.ui.screens import (
    MusicScreen, VolumeScreen, PowerScreen, WaitingScreen, BTMenuScreen
)

class UIRenderer:
    def __init__(self):
        self.screens = {
            "music": MusicScreen(),
            "volume": VolumeScreen(),
            "power": PowerScreen(),
            "waiting": WaitingScreen(),
            "bt_menu": BTMenuScreen()
        }

    def render(self, display, state, bt_manager):
        if state.current_media_type == "qr" and getattr(state, "current_playing", False):
            return

        # Decide which screen to draw
        with display.canvas() as draw:
            # 1. Power/Shutdown Screen
            if state.is_shutting_down:
                self.screens["power"].draw(draw, state, bt_manager)
            
            # 2. BT Menu Screen
            elif state.current_state == 1: # STATE_BT_MENU
                self.screens["bt_menu"].draw(draw, state, bt_manager)
                
            # 3. Volume Screen Overlay
            elif time.time() < state.show_volume_until:
                self.screens["volume"].draw(draw, state, bt_manager)
                
            # 4. Active Playback screen
            elif state.current_uid is not None:
                self.screens["music"].draw(draw, state, bt_manager)
                
            # 5. Waiting/Standby Screen
            else:
                self.screens["waiting"].draw(draw, state, bt_manager)
