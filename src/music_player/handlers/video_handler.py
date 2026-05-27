import os
from music_player.handlers.base_handler import BaseHandler
from music_player.video_player import play_preprocessed_bin

class VideoHandler(BaseHandler):
    def play(self, assets, state, hardware_dict):
        video_file = assets.get("video")
        audio_file = assets.get("audio") # Get audio file defined in catalog.json!
        print(f"Loading Video: {state.current_title} ({video_file}) -> audio: {audio_file}")
        
        display = hardware_dict["display"].device
        nfc_reader = hardware_dict["nfc_reader"]
        button_controller = hardware_dict["button_controller"]

        def check_tag_removed():
            uid = nfc_reader.read_passive_target(timeout=0.05)
            return uid is None

        if video_file and os.path.exists(video_file):
            # Intercept display loop and play video frames sequentially
            play_preprocessed_bin(
                video_file,
                display=display,
                check_tag_removed_fn=check_tag_removed,
                vol_up_btn=button_controller.vol_up_btn,
                vol_down_btn=button_controller.vol_down_btn,
                get_volume_fn=lambda: state.volume,
                set_volume_fn=state.set_volume,
                audio_path=audio_file # Pass the catalog.json audio path!
            )
        else:
            print("Video file not found!")

        # After video completes or is canceled:
        state.current_uid = None
        state.current_playing = False

    def stop(self, state, hardware_dict):
        # Already self-terminates on tag removal or completion, but let's clear state
        state.current_playing = False
