import time
import pygame
from music_player.state.config import VOLUME_DEFAULT, VOLUME_MAX, VOLUME_MIN

class PlayerState:
    def __init__(self):
        self.volume = VOLUME_DEFAULT
        self.show_volume_until = 0.0
        self.is_shutting_down = False
        
        # State Management for Menus (0: Playing, 1: BT Menu)
        self.current_state = 0
        self.menu_index = 0
        self.menu_message = ""
        self.menu_message_timeout = 0.0
        
        # Tag tracking
        self.current_uid = None
        self.current_playing = False
        self.current_title = ""
        self.current_artwork_img = None
        self.current_media_type = "audio"
        
        # Radio state
        self.radio_tune_start_time = 0.0
        self.current_station_freq = "96.7"
        
        # Slideshow state
        self.slideshow_images = []
        self.slideshow_index = 0
        self.next_slide_time = 0.0
        
        # Frame counter
        self.frame_counter = 0

    @property
    def is_playing(self):
        return self.current_playing

    def set_volume(self, new_vol):
        self.volume = max(VOLUME_MIN, min(VOLUME_MAX, new_vol))
        pygame.mixer.music.set_volume(self.volume / 10.0)
        self.show_volume_until = time.time() + 2.0

    def trigger_volume_overlay(self):
        self.show_volume_until = time.time() + 2.0
