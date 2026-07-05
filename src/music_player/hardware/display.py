from contextlib import contextmanager
from luma.core.interface.serial import i2c
from luma.oled.device import sh1106
from PIL import Image, ImageDraw, ImageOps
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

