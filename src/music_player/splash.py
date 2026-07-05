import sys
from music_player.hardware.display import Display

def main():
    # Initialize OLED
    display = Display()

    # Prevent Luma from wiping the screen when the script exits
    if display.device:
        display.device.cleanup = lambda: None

        with display.canvas() as draw:
            if len(sys.argv) > 1 and "stop" in sys.argv:
                draw.text((28, 28), "SHUTTING DOWN...", fill="white")
            else:
                draw.text((40, 28), "BOOTING...", fill="white")

if __name__ == "__main__":
    main()

