from PIL import Image
from music_player.handlers.base_handler import BaseHandler

try:
    import qrcode
except ImportError:  # pragma: no cover - optional dependency
    qrcode = None


class QRHandler(BaseHandler):
    """Display QR-code content from a catalog entry on the OLED display."""

    def __init__(self):
        self._last_text = None

    def play(self, assets, state, hardware_dict):
        text = assets.get("text") or assets.get("url") or ""
        if not text:
            state.current_playing = False
            return
        self._display_qr(text, state, hardware_dict)
        state.current_playing = True
        self._last_text = text

    def update(self, state, hardware_dict):
        if not getattr(state, "current_playing", False):
            return
        text = self._last_text or ""
        if text:
            self._display_qr(text, state, hardware_dict)

    def stop(self, state, hardware_dict):
        state.current_playing = False
        self._last_text = None

    def _display_qr(self, text, state, hardware_dict):
        display = hardware_dict.get("display")
        if display is None or not hasattr(display, "display"):
            return

        if qrcode is None:
            self._display_fallback_text(text, display)
            return

        try:
            qr_code = qrcode.QRCode(
                version=2,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=3,
                border=1,
            )
            qr_code.add_data(text)
            qr_code.make(fit=True)
            qr_image = qr_code.make_image(fill_color="black", back_color="white").convert("1")

            # Scale down to fit the OLED while keeping the QR readable.
            qr_image = qr_image.resize((64, 64), Image.Resampling.LANCZOS)
            canvas = Image.new("1", (128, 64), 0)
            canvas.paste(qr_image, (32, 0))
            display.display(canvas)
        except Exception as exc:  # pragma: no cover - defensive branch
            print(f"[-] Failed to render QR code: {exc}")
            self._display_fallback_text(text, display)

    def _display_fallback_text(self, text, display):
        try:
            from PIL import ImageDraw, ImageFont
        except ImportError:  # pragma: no cover - optional dependency
            return

        img = Image.new("1", (128, 64), 0)
        draw = ImageDraw.Draw(img)
        font = ImageFont.load_default()
        draw.text((2, 2), "QR", fill=1, font=font)
        draw.text((2, 20), text[:18], fill=1, font=font)
        display.display(img)
