from PIL import Image
from luma.core.interface.serial import i2c
from luma.oled.device import sh1106
import time

def main():
    # 1. Initialize the I2C interface and the SH1106 screen
    # (Default I2C address for these displays is usually 0x3C)
    serial = i2c(port=1, address=0x3C)
    device = sh1106(serial)

    # 2. Load your Procreate artwork
    # Make sure 'my_artwork.png' is in the same folder as this script
    try:
        img = Image.open("/home/user/Pictures/image1.png")
    except FileNotFoundError:
        print("Could not find your image file! Check the path.")
        return

    # 3. Defensive scaling (just in case your canvas wasn't exactly 128x64)
    if img.size != (128, 64):
        print(f"Warning: Image size is {img.size}, resizing to 128x64.")
        img = img.resize((128, 64), Image.Resampling.NEAREST)

    # 4. Convert image to 1-bit monochrome ("1" mode) 
    # This automatically flattens colors/grays cleanly.
    monochrome_img = img.convert("1")

    print("Displaying image on OLED...")
    device.display(monochrome_img)

    # Keep the script alive for a few seconds so you can admire your work
    time.sleep(10)

if __name__ == "__main__":
    main()
