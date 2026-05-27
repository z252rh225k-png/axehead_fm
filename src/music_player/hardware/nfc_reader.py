import serial
from adafruit_pn532.uart import PN532_UART
from music_player.state.config import NFC_SERIAL_PORT, NFC_BAUDRATE

class NFCReader:
    def __init__(self):
        try:
            self.uart_device = serial.Serial(NFC_SERIAL_PORT, baudrate=NFC_BAUDRATE, timeout=0.1)
            self.pn532 = PN532_UART(self.uart_device, debug=False)
            self.pn532.SAM_configuration()
            print("[+] NFC PN532 initialized successfully.")
        except Exception as e:
            print(f"[-] Failed to initialize NFC Reader: {e}")
            self.pn532 = None

    def read_passive_target(self, timeout=0.05):
        if not self.pn532:
            return None
        try:
            return self.pn532.read_passive_target(timeout=timeout)
        except Exception as e:
            print(f"[-] NFC read target error: {e}")
            return None

    def ntag2xx_read_block(self, block_num):
        if not self.pn532:
            return None
        try:
            return self.pn532.ntag2xx_read_block(block_num)
        except Exception as e:
            print(f"[-] NFC read block {block_num} error: {e}")
            return None
