import os
import time
from music_player.handlers.base_handler import BaseHandler
from music_player.state.config import AUDIO_FADE_IN, AUDIO_FADE_OUT

class AudioHandler(BaseHandler):
    def __init__(self):
        self.fade_in_start_time = None
        self.fade_in_duration_ms = 0
        self.fade_in_target_volume = 0.5
        
        self.fade_out_start_time = None
        self.fade_out_duration_ms = 0
    
    def play(self, assets, state, hardware_dict):
        audio_engine = hardware_dict["audio_engine"]
        file_path = assets.get("audio", "")
        if file_path and os.path.exists(file_path):
            print(f"Playing audio: {state.current_title} ({file_path})")
            audio_engine.load(file_path)
            
            # Store target volume for fade in
            self.fade_in_target_volume = state.volume / 10.0
            
            # Play with loops=-1 (infinite) - will loop until tag is removed
            audio_engine.play(loops=-1)
            
            # Setup fade in if configured
            fade_in_seconds = AUDIO_FADE_IN
            if fade_in_seconds > 0:
                # Start with volume 0 for fade in
                audio_engine.set_volume(0.0)
                self.fade_in_start_time = time.time()
                self.fade_in_duration_ms = int(fade_in_seconds * 1000)
                print(f"[+] Starting fade in over {fade_in_seconds}s")
            else:
                # No fade in, set to target volume immediately
                audio_engine.set_volume(self.fade_in_target_volume)
                self.fade_in_start_time = None
            
            state.current_playing = True
            self.fade_out_start_time = None
        else:
            print("Audio file not found on device.")
            state.current_playing = False

    def update(self, state, hardware_dict):
        """Called periodically to handle fade in/out progress."""
        audio_engine = hardware_dict["audio_engine"]
        
        # Handle fade in in progress
        if self.fade_in_start_time is not None:
            elapsed_ms = (time.time() - self.fade_in_start_time) * 1000
            if elapsed_ms >= self.fade_in_duration_ms:
                # Fade in complete, set to target volume
                audio_engine.set_volume(self.fade_in_target_volume)
                self.fade_in_start_time = None
            else:
                # Continue fading in
                progress = elapsed_ms / self.fade_in_duration_ms
                current_volume = self.fade_in_target_volume * progress
                audio_engine.set_volume(current_volume)
        
        # Check if fade out was initiated and has completed
        if self.fade_out_start_time is not None:
            elapsed_ms = (time.time() - self.fade_out_start_time) * 1000
            if elapsed_ms >= self.fade_out_duration_ms:
                # Fade out complete, ensure audio is stopped
                audio_engine.stop()
                state.current_playing = False
                self.fade_out_start_time = None
    
    def stop(self, state, hardware_dict):
        """Stop audio with fade out when tag is removed."""
        audio_engine = hardware_dict["audio_engine"]
        fade_out_ms = int(AUDIO_FADE_OUT * 1000)  # Convert seconds to milliseconds
        
        if fade_out_ms <= 0:
            # No fade, stop immediately
            audio_engine.stop()
            state.current_playing = False
        else:
            # Use pygame's built-in fadeout
            audio_engine.fade_out(fade_out_ms)
            self.fade_out_start_time = time.time()
            self.fade_out_duration_ms = fade_out_ms
        state.current_playing = False
