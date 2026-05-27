from luma.core.interface.serial import i2c
from luma.oled.device import sh1106

class Display:
    def __init__(self):
        try:
            self.serial_i2c = i2c(port=1, address=0x3C)
            self.device = sh1106(self.serial_i2c)
            print("[+] OLED Display initialized successfully.")
        except Exception as e:
            print(f"[-] Failed to initialize OLED Display: {e}")
            self.device = None
