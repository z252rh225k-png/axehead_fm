#!/usr/bin/env python3
"""
Simple OLED screen tester for Mac development.
Displays screens in a simulated window without needing hardware.

WORKFLOW:
  1. Set up once: make sure macos_venv is installed with pygame
  2. Run screens:  ./test_screen.sh [screen_name]
     OR manually:  source macos_venv/bin/activate && PYTHONPATH=src python3 screen_tester.py [screen_name]

Available screens:
    waiting  - Idle/standby screen with clock
    music    - Music playback screen
    volume   - Volume overlay
    power    - Power/shutdown screen
    bt_menu  - Bluetooth menu screen

Press ESC or close window to exit.
"""

import sys
import time
import pygame
from PIL import Image, ImageDraw
from music_player.state.player_state import PlayerState
from music_player.ui.renderer import UIRenderer


class MockBluetoothManager:
    """Mock Bluetooth manager for testing."""
    def __init__(self):
        self.connected_device = None


class ScreenTester:
    DISPLAY_WIDTH = 128
    DISPLAY_HEIGHT = 64
    SCALE = 1  # Scale up the display for visibility on Mac
    FPS = 30
    
    def __init__(self, screen_name="waiting"):
        self.screen_name = screen_name
        self.state = PlayerState()
        self.bt_manager = MockBluetoothManager()
        self.renderer = UIRenderer()
        
        pygame.init()
        self.width = self.DISPLAY_WIDTH * self.SCALE
        self.height = self.DISPLAY_HEIGHT * self.SCALE
        self.screen = pygame.display.set_mode((self.width, self.height))
        
        self.clock = pygame.time.Clock()
        self.frame_count = 0
        self.running = True
        
        # Font for info text
        self.font = pygame.font.Font(None, 24)
    
    def render_screen(self):
        """Render the current screen to PIL Image."""
        # Create blank 1-bit image (like OLED)
        img = Image.new("1", (self.DISPLAY_WIDTH, self.DISPLAY_HEIGHT), color=0)
        draw = ImageDraw.Draw(img)
        
        # Set screen state based on name
        if self.screen_name == "waiting":
            self.state.current_uid = None
            self.state.is_shutting_down = False
            self.state.current_state = 0
        elif self.screen_name == "music":
            self.state.current_uid = "test_uid"
            self.state.current_title = "Test Song"
            self.state.current_playing = True
        elif self.screen_name == "volume":
            self.state.show_volume_until = time.time() + 10
            self.state.volume = 7
        elif self.screen_name == "power":
            self.state.is_shutting_down = True
        elif self.screen_name == "bt_menu":
            self.state.current_state = 1
        
        # Update frame counter for animations
        self.state.frame_counter += 1
        
        # Draw the screen
        if self.screen_name in self.renderer.screens:
            self.renderer.screens[self.screen_name].draw(draw, self.state, self.bt_manager)
        
        return img
    
    def update_display(self):
        """Update the pygame display with the rendered screen."""
        # Render screen
        img = self.render_screen()
        
        # Convert 1-bit to RGB for display
        img_rgb = img.convert("RGB")
        
        # Scale up for visibility
        scaled_img = img_rgb.resize(
            (self.DISPLAY_WIDTH * self.SCALE, self.DISPLAY_HEIGHT * self.SCALE),
            Image.NEAREST
        )
        
        # Convert PIL image to pygame surface
        mode = scaled_img.mode
        size = scaled_img.size
        data = scaled_img.tobytes()
        pygame_surface = pygame.image.fromstring(data, size, mode)
        
        # Clear screen and draw
        self.screen.fill((0, 0, 0))
        self.screen.blit(pygame_surface, (0, 0))
        
        pygame.display.flip()
    
    def run(self):
        """Start the screen tester."""
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
            
            self.update_display()
            self.clock.tick(self.FPS)
        
        pygame.quit()


if __name__ == "__main__":
    screen = sys.argv[1] if len(sys.argv) > 1 else "waiting"
    
    valid_screens = ["waiting", "music", "volume", "power", "bt_menu"]
    if screen not in valid_screens:
        print(f"Invalid screen '{screen}'")
        print(f"Valid options: {', '.join(valid_screens)}")
        sys.exit(1)
    
    tester = ScreenTester(screen)
    tester.run()
