import time
import math
from music_player.ui.screens.base_screen import BaseScreen
from music_player.ui.assets import draw_bluetooth_icon

class WaitingScreen(BaseScreen):
    """Displays a classic 1-bit bouncing DVD logo screensaver."""
    
    def __init__(self):
        # Assuming a standard 128x64 OLED display based on previous layouts
        self.display_width = 128
        self.display_height = 64
        
        # Define the size of our miniature DVD logo
        self.logo_w = 32
        self.logo_h = 16
        
        # Set starting position
        self.x = 50
        self.y = 25
        
        # Set movement speed and direction (pixels per frame)
        # Change these to 1 for a slower, smoother glide
        self.dx = 1
        self.dy = 1 

    def draw(self, draw, state, bt_manager):
        # 1. Update position based on current velocity
        self.x += self.dx
        self.y += self.dy
        
        # 2. Check for collisions with screen edges and bounce
        # Left edge
        if self.x <= 0:
            self.x = 0
            self.dx *= -1
        # Right edge
        elif self.x + self.logo_w >= self.display_width:
            self.x = self.display_width - self.logo_w
            self.dx *= -1
            
        # Top edge
        if self.y <= 0:
            self.y = 0
            self.dy *= -1
        # Bottom edge
        elif self.y + self.logo_h >= self.display_height:
            self.y = self.display_height - self.logo_h
            self.dy *= -1
            
        # 3. Draw the stylized 1-bit DVD logo at the new coordinates
        
        # # The main outer box
        # draw.rectangle(
        #     (self.x, self.y, self.x + self.logo_w, self.y + self.logo_h),
        #     outline="white", fill="black"
        # )
        
        # The classic squashed ellipse underneath the text
        draw.ellipse(
            (self.x + 2, self.y + 8, self.x + self.logo_w - 2, self.y + 12),
            outline="white", width=2
        )
        
        # The text itself (manually positioned to center inside our box)
        draw.text((self.x + 5, self.y), "DVD", fill="white")