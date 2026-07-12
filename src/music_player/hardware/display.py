from contextlib import contextmanager
from luma.core.interface.serial import i2c
from luma.oled.device import sh1106
from PIL import Image, ImageDraw, ImageOps, ImageFont
from music_player.state.config import INVERT_DISPLAY

class Display:
    def __init__(self):
        try:
            self.serial_i2c = i2c(port=1, address=0x3C)
            self.device = sh1106(self.serial_i2c)
            print("[+] OLED Display initialized successfully.")
        except Exception as e:
            print(f"[-] Failed to initialize OLED Display: {e}")
            self.device = None

    @contextmanager
    def canvas(self):
        """Context manager for drawing that auto-inverts the image if INVERT_DISPLAY is True."""
        # Create a blank black image (0 = black in 1-bit mode)
        img = Image.new("1", (128, 64), color=0)
        draw = ImageDraw.Draw(img)
        
        yield draw
        
        # After drawing completes, display (with inversion if needed)
        self._display_image(img)

    def _display_image(self, img, invert=True):
        """Internal method to display an image with optional inversion."""
        if invert and INVERT_DISPLAY and img:
            # Invert: black becomes white, white becomes black
            inverted_img = ImageOps.invert(img.convert("L")).convert("1")
            self.device.display(inverted_img)
        else:
            self.device.display(img)

    def display(self, img, invert=True):
        """Display an image on the OLED, inverting it if INVERT_DISPLAY is True.
        
        Args:
            img: PIL Image to display
            invert: Whether to apply inversion if INVERT_DISPLAY is set (default True)
        """
        self._display_image(img, invert=invert)

    @staticmethod
    def draw_progress_bar(draw, progress_percent, x, y, width, height, label=""):
        """Draw a progress bar on an ImageDraw object.
        
        Args:
            draw: PIL ImageDraw object
            progress_percent: Progress percentage (0-100)
            x, y: Top-left coordinates
            width: Bar width in pixels
            height: Bar height in pixels
            label: Optional label text above the bar
        """
        # Clamp progress to 0-100
        progress_percent = max(0, min(100, progress_percent))
        
        # Draw label if provided
        if label:
            try:
                # Try to use a small font if available
                font = ImageFont.load_default()
            except:
                font = None
            draw.text((x, y - 10), label, fill=1, font=font)
        
        # Draw bar outline (unfilled rectangle)
        draw.rectangle(
            [(x, y), (x + width, y + height)],
            outline=1,
            fill=0
        )
        
        # Draw filled portion (left to right)
        # Interior is 2 pixels smaller (1 pixel margin on each side)
        inner_width = width - 2
        filled_width = int((progress_percent / 100.0) * inner_width)
        
        if filled_width > 0:
            # Ensure we have at least 1 pixel of fill when progress > 0
            filled_width = max(1, filled_width)
            x0 = x + 1
            x1 = x + 1 + filled_width
            # Ensure x1 doesn't exceed the bar boundary
            x1 = min(x1, x + width - 1)
            
            draw.rectangle(
                [(x0, y + 1), (x1, y + height - 1)],
                fill=1
            )
        
        # Draw percentage text centered below bar
        try:
            font = ImageFont.load_default()
        except:
            font = None
        
        percent_text = f"{int(progress_percent)}%"
        # Simple text positioning - assume font is ~6 pixels wide per char
        text_x = x + (width // 2) - (len(percent_text) * 3)
        text_y = y + height + 2
        draw.text((text_x, text_y), percent_text, fill=1, font=font)


