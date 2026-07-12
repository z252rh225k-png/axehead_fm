import pygame
from music_player.state.config import VOLUME_DEFAULT
from music_player.hardware.audio_device_manager import AudioDeviceManager

class AudioEngine:
    def __init__(self):
        self.mixer_initialized = False
        
        try:
            # Standard initialization: 44.1kHz, 16-bit stereo, with sufficient buffer for USB latency
            pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=4096)
            pygame.mixer.init()
            self.mixer_initialized = True
            print("[+] Audio Engine initialized successfully.")
        except Exception as e:
            print(f"[-] Audio mixer initialization failed: {e}")
        
        # Initialize audio device manager to handle headphone detection
        self.device_manager = AudioDeviceManager()
        self.device_manager.start_monitor()
        print("[+] Audio Device Manager started")
        
        # Set initial volume only if mixer actually initialized
        if self.mixer_initialized:
            pygame.mixer.music.set_volume(VOLUME_DEFAULT / 10.0)
        else:
            print("[!] Mixer not initialized - audio playback disabled. Check /home/user/.asoundrc config.")

    def stop(self):
        if self.mixer_initialized:
            pygame.mixer.music.stop()

    def load(self, file_path):
        if self.mixer_initialized:
            pygame.mixer.music.load(file_path)

    def play(self, loops=-1):
        """Play audio with looping. loops=-1 means infinite loop."""
        if self.mixer_initialized:
            pygame.mixer.music.play(loops)

    def set_volume(self, volume_scale):
        if self.mixer_initialized:
            pygame.mixer.music.set_volume(volume_scale)
    
    def fade_out(self, duration_ms=1000):
        """Fade out audio over specified duration (in milliseconds)."""
        if self.mixer_initialized:
            pygame.mixer.music.fadeout(int(duration_ms))

    def quit(self):
        try:
            self.device_manager.stop_monitor()
        except Exception as e:
            print(f"[-] Error stopping device manager: {e}")
        
        if self.mixer_initialized:
            try:
                pygame.mixer.quit()
                pygame.quit()
            except Exception as e:
                print(f"[-] Pygame quit error: {e}")
