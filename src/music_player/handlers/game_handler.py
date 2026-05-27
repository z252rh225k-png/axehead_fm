from music_player.handlers.base_handler import BaseHandler
from music_player.game_engine import run_snake_game

class GameHandler(BaseHandler):
    def play(self, assets, state, hardware_dict):
        print(f"Loading Game: {state.current_title}")
        
        display = hardware_dict["display"].device
        nfc_reader = hardware_dict["nfc_reader"]
        button_controller = hardware_dict["button_controller"]

        def check_tag_removed():
            uid = nfc_reader.read_passive_target(timeout=0.05)
            return uid is None

        # This completely intercepts control until tag is removed!
        run_snake_game(
            display,
            nfc_reader.pn532,
            button_controller.vol_up_btn,
            button_controller.vol_down_btn,
            check_tag_removed
        )
        
        # Once game exits, clear tag presence to avoid instant re-trigger
        state.current_uid = None
        state.current_playing = False

    def stop(self, state, hardware_dict):
        state.current_playing = False
