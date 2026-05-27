import pygame
from music_player.state.config import VOLUME_DEFAULT

class AudioEngine:
    def __init__(self):
        try:
            pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=8192)
            pygame.mixer.init()
            print("[+] Audio Engine pre-initialized successfully.")
        except Exception as e:
            print(f"[-] Pygame mixer pre-init failed: {e}. Falling back to standard init...")
            try:
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=8192)
                print("[+] Audio Engine fallback init successful.")
            except Exception as e2:
                print(f"[-] Pygame mixer fallback init failed: {e2}")
        
        # Set initial volume
        pygame.mixer.music.set_volume(VOLUME_DEFAULT / 10.0)

    def stop(self):
        pygame.mixer.music.stop()

    def load(self, file_path):
        pygame.mixer.music.load(file_path)

    def play(self, loops=0):
        pygame.mixer.music.play(loops)

    def set_volume(self, volume_scale):
        pygame.mixer.music.set_volume(volume_scale)

    def quit(self):
        try:
            pygame.mixer.quit()
            pygame.quit()
        except Exception as e:
            print(f"[-] Pygame quit error: {e}")
