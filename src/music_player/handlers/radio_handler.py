import subprocess
import time
from music_player.handlers.base_handler import BaseHandler

class RadioHandler(BaseHandler):
    def __init__(self):
        self.active_radio_process = None

    def play(self, assets, state, hardware_dict):
        stream_url = assets.get("stream_url", "")
        state.current_station_freq = assets.get("station_freq", "96.7")
        state.radio_tune_start_time = time.time() # Mark start of retro search sweep!
        print(f"Streaming radio: {state.current_title} ({stream_url})")
        
        if stream_url:
            try:
                # Launch headless command line player for internet radio streams
                self.active_radio_process = subprocess.Popen(
                    ["mpv", "--no-video", stream_url],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                state.current_playing = True
            except Exception as e:
                print(f"[-] Failed to launch radio process: {e}")
                state.current_playing = False
        else:
            state.current_playing = False

    def stop(self, state, hardware_dict):
        if self.active_radio_process:
            try:
                self.active_radio_process.terminate()
                self.active_radio_process.wait()
            except Exception as e:
                print(f"[-] Error terminating radio process: {e}")
            self.active_radio_process = None
        state.current_playing = False
