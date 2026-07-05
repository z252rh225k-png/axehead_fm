import time

try:
    from luma.core.render import canvas
except ImportError:  # pragma: no cover - optional dependency
    canvas = None

try:
    from PIL import ImageDraw, ImageFont
except ImportError:  # pragma: no cover - optional dependency
    ImageDraw = None
    ImageFont = None


class WiFiSetupScreen:
    """Minimal Wi-Fi provisioning screen for the display."""

    def __init__(self, font_path: str = None):
        self.font = None
        self.status = "scanning"
        self.message = ""
        self.start_time = time.time()
        if font_path and ImageFont is not None:
            try:
                self.font = ImageFont.truetype(font_path, 10)
            except Exception:
                self.font = None

    def render(self, display) -> None:
        if canvas is None or ImageDraw is None:
            return
        with canvas(display) as img:
            draw = ImageDraw.Draw(img)
            draw.text((5, 5), "WiFi Setup", fill="white", font=self.font)
            draw.text((5, 20), self.message[:20] or "Waiting...", fill="white", font=self.font)
            dots = "." * (int(time.time()) % 4)
            draw.text((5, 36), f"{self.status}{dots}", fill="white", font=self.font)
