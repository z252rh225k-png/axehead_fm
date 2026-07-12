import os

# Centralized configuration and paths
# Built-in catalog (read-only, deployed via ansible)
BUILTIN_CATALOG_PATH = "/opt/music-player/catalog.json"
LOCAL_BUILTIN_CATALOG_FALLBACK = "catalog.json"

# User catalog (editable via web UI, persists across deployments)
USER_CATALOG_PATH = "/opt/music-player/user_catalog.json"
LOCAL_USER_CATALOG_FALLBACK = "user_catalog.json"

# Deprecated: kept for backward compatibility
CATALOG_PATH = BUILTIN_CATALOG_PATH
LOCAL_CATALOG_FALLBACK = LOCAL_BUILTIN_CATALOG_FALLBACK

# Built-in media (deployed via ansible)
BUILTIN_MEDIA_PATH = "/opt/music-player/media"
LOCAL_BUILTIN_MEDIA_FALLBACK = "media"

# User media (editable via web UI, persists across deployments)
USER_MEDIA_PATH = "/opt/music-player/user_media"
LOCAL_USER_MEDIA_FALLBACK = "user_media"

USER_CONFIG_PATH = "/opt/music-player/config.json"
LOCAL_USER_CONFIG_FALLBACK = "config.json"

# Load user-defined settings with default values fallback
import json

_defaults = {
    "invert_display": False,
    "volume_default": 5,
    "volume_max": 10,
    "volume_min": 0,
    "volume_overlay_duration": 2.0,
    "radio_tuning_duration": 2.5,
    "radio_default_freq": "96.7",
    "nfc_serial_port": "/dev/serial0",
    "nfc_baudrate": 115200,
    "button_vol_up_pin": 17,
    "button_vol_down_pin": 27,
    "button_hold_time": 1.5,
    "wifi_config": {},
    "hotspot_ssid": "AxeheadFM",
    "hotspot_password": "pi1234567",
    "wifi_setup_enabled": True,
    "audio_fade_in": 0.05,
    "audio_fade_out": 0.1
}

def load_user_config():
    config = _defaults.copy()
    paths_to_try = [USER_CONFIG_PATH, LOCAL_USER_CONFIG_FALLBACK]
    for path in paths_to_try:
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    user_data = json.load(f)
                    if isinstance(user_data, dict):
                        for k, v in user_data.items():
                            lower_k = k.lower()
                            if lower_k in config:
                                config[lower_k] = v
                            else:
                                config[k] = v
                break
            except Exception as e:
                print(f"[-] Failed to load config from {path}: {e}")
    return config

_active_config = load_user_config()
# Export configurations
INVERT_DISPLAY = _active_config.get("invert_display", False)

# Hardware Configuration
NFC_SERIAL_PORT = _active_config.get("nfc_serial_port", "/dev/serial0")
NFC_BAUDRATE = _active_config.get("nfc_baudrate", 115200)

BUTTON_VOL_UP_PIN = _active_config.get("button_vol_up_pin", 17)
BUTTON_VOL_DOWN_PIN = _active_config.get("button_vol_down_pin", 27)
BUTTON_HOLD_TIME = _active_config.get("button_hold_time", 1.5)

VOLUME_DEFAULT = _active_config.get("volume_default", 5)
VOLUME_MAX = _active_config.get("volume_max", 10)
VOLUME_MIN = _active_config.get("volume_min", 0)
VOLUME_OVERLAY_DURATION = _active_config.get("volume_overlay_duration", 2.0)  # seconds

# Audio fade settings (seconds)
AUDIO_FADE_IN = _active_config.get("audio_fade_in", 0.0)
AUDIO_FADE_OUT = _active_config.get("audio_fade_out", 1.0)
# Radio config
RADIO_TUNING_DURATION = _active_config.get("radio_tuning_duration", 2.5)  # seconds
RADIO_DEFAULT_FREQ = _active_config.get("radio_default_freq", "96.7")

# Wi-Fi provisioning config
WIFI_CONFIG = _active_config.get("wifi_config", {})
HOTSPOT_SSID = _active_config.get("hotspot_ssid", "AxeheadFM")
HOTSPOT_PASSWORD = _active_config.get("hotspot_password", "pi1234567")
WIFI_SETUP_ENABLED = _active_config.get("wifi_setup_enabled", True)

