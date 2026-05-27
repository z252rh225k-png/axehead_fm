import os

# Centralized configuration and paths
CATALOG_PATH = "/opt/music-player/catalog.json"
LOCAL_CATALOG_FALLBACK = "catalog.json"

# Hardware Configuration
NFC_SERIAL_PORT = "/dev/serial0"
NFC_BAUDRATE = 115200

BUTTON_VOL_UP_PIN = 17
BUTTON_VOL_DOWN_PIN = 27
BUTTON_HOLD_TIME = 1.5

VOLUME_DEFAULT = 5
VOLUME_MAX = 10
VOLUME_MIN = 0
VOLUME_OVERLAY_DURATION = 2.0  # seconds

# Radio config
RADIO_TUNING_DURATION = 2.5  # seconds
RADIO_DEFAULT_FREQ = "96.7"
