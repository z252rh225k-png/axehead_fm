import sys
from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import sh1106

def main():
    # Initialize OLED
    serial_i2c = i2c(port=1, address=0x3C)
    display = sh1106(serial_i2c)

    # Prevent Luma from wiping the screen when the script exits
    display.cleanup = lambda: None

    with canvas(display) as draw:
        if len(sys.argv) > 1 and "stop" in sys.argv:
            draw.text((28, 28), "SHUTTING DOWN...", fill="white")
        else:
            draw.text((40, 28), "BOOTING...", fill="white")

if __name__ == "__main__":
    main()
