import re
from typing import Optional, Dict

try:
    import serial
except ImportError:  # pragma: no cover - optional dependency
    serial = None

try:
    from adafruit_pn532.uart import PN532_UART
except ImportError:  # pragma: no cover - optional dependency
    PN532_UART = None

from music_player.state.config import NFC_SERIAL_PORT, NFC_BAUDRATE


class NFCReader:
    def __init__(self):
        self.pn532 = None
        self._init_error = None
        try:
            if serial is None:
                raise ImportError("pyserial not available")
            if PN532_UART is None:
                raise ImportError("adafruit_pn532 not available")
            self.uart_device = serial.Serial(NFC_SERIAL_PORT, baudrate=NFC_BAUDRATE, timeout=0.1)
            self.pn532 = PN532_UART(self.uart_device, debug=False)
            self.pn532.SAM_configuration()
            print("[+] NFC PN532 initialized successfully.")
        except Exception as e:
            self._init_error = str(e)
            print(f"[-] Failed to initialize NFC Reader: {e}")

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

    def read_wifi_payload(self, timeout: float = 0.05) -> Optional[str]:
        """Read a simple text payload from an NFC tag for Wi-Fi provisioning."""
        raw_data = bytearray()
        try:
            for block_num in range(4, 20):
                block = self.ntag2xx_read_block(block_num)
                if block:
                    raw_data.extend(block)
        except Exception as e:  # pragma: no cover - defensive branch
            print(f"[-] NFC Wi-Fi read error: {e}")
            return None

        if not raw_data:
            return None
        return raw_data.decode("ascii", errors="ignore").strip() or None


def is_wifi_tag(tag_id: Optional[str], payload: Optional[str]) -> bool:
    if not tag_id and not payload:
        return False
    text = " ".join([tag_id or "", payload or ""])
    return bool(re.search(r"(nfc_wifi|ssid=|pass=|password=|wifi)", text, re.IGNORECASE))


def parse_wifi_ndef(payload: Optional[str]) -> Optional[Dict[str, str]]:
    """Parse simple Wi-Fi provisioning payloads."""
    if not payload:
        return None

    text = payload.strip()
    if not text:
        return None

    if "|" in text and "ssid=" not in text.lower():
        parts = [part.strip() for part in text.split("|") if part.strip()]
        if len(parts) >= 2:
            return {"ssid": parts[0], "password": parts[1], "security": "WPA2"}

    wifi_config = {"ssid": None, "password": None, "security": "WPA2"}
    for key, value in re.findall(r"([a-z]+)=([^|]+)", text, re.IGNORECASE):
        key_lower = key.lower()
        if key_lower in {"ssid", "network"}:
            wifi_config["ssid"] = value.strip()
        elif key_lower in {"pass", "password", "key"}:
            wifi_config["password"] = value.strip()
        elif key_lower in {"auth", "security", "type"}:
            wifi_config["security"] = value.strip().upper()

    if wifi_config["ssid"] and wifi_config["password"]:
        return wifi_config
    return None
