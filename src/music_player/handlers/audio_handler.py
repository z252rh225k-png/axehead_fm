import os
import pygame
from music_player.handlers.base_handler import BaseHandler

class AudioHandler(BaseHandler):
    def play(self, assets, state, hardware_dict):
        audio_engine = hardware_dict["audio_engine"]
        file_path = assets.get("audio", "")
        if file_path and os.path.exists(file_path):
            print(f"Playing audio: {state.current_title} ({file_path})")
            audio_engine.load(file_path)
            audio_engine.play()
            state.current_playing = True
        else:
            print("Audio file not found on device.")
            state.current_playing = False

    def stop(self, state, hardware_dict):
        audio_engine = hardware_dict["audio_engine"]
        audio_engine.stop()
        state.current_playing = False
