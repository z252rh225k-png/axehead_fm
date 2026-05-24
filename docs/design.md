---
name: Raspberry Pi NFC Music Player Architecture
description: Core context, pinouts, and systemd service layouts for the Analog Music Player.
alwaysApply: true
---

# Project Context: Analog NFC Music Player

This document serves as the master source of truth for the physical computing setup, paths, and daemon configurations of the headless Raspberry Pi music player.

## 🛠️ Hardware Landscape & Pinout

| Peripheral | Component / Protocol | Pin / GPIO | Notes |
| :--- | :--- | :--- | :--- |
| **Display** | SH1106 Monochrome OLED | I2C (Bus 1, Addr `0x3C`) | Controlled via `luma.oled` library |
| **Token Reader** | PN532 NFC Module | SPI or I2C | Triggers music playback based on tag IDs |
| **Safe Shutdown** | Physical Tactile Button | GPIO 22 (Pin 15) | Handled **natively by OS kernel** via `dtoverlay=gpio-shutdown,gpio_pin=22` in `/boot/firmware/config.txt`. **DO NOT claim this pin in Python code.** |

---

## 📂 Environment & Directory Structures

* **Working Directory:** `/home/user/src/`
* **Main Script:** `/home/user/src/player.py`
* **Splash Script:** `/home/user/src/splash.py` (Handles instant boot/shutdown text)
* **Python Virtual Env:** `/home/user/oled_test_env/` (Running Python 3.13)
* **Audio Backend:** PipeWire (Raspberry Pi OS Bookworm default)

---

## ⚙️ System Daemons (systemd)

### 1. Main Player Service (`/etc/systemd/system/musicplayer.service`)
```ini
[Unit]
Description=Analog NFC Music Player Service
After=sound.target alsa-state.target
DefaultDependencies=no

[Service]
Type=simple
User=user
Group=user
SupplementaryGroups=audio input
WorkingDirectory=/home/user/src
Environment=XDG_RUNTIME_DIR=/run/user/1000
Environment=DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus
Environment=PYTHONUNBUFFERED=1
ExecStart=/home/user/oled_test_env/bin/python3 /home/user/src/player.py
ExecStopPost=/home/user/oled_test_env/bin/python3 /home/user/src/splash.py stop
TimeoutStopSec=2s
SendSIGKILL=yes
Restart=on-failure
RestartSec=2

[Install]
WantedBy=basic.target

2. Fast Boot Splash Service (/etc/systemd/system/bootsplash.service)
Ini, TOML
[Unit]
Description=Instant OLED Boot Splash
DefaultDependencies=no
After=systemd-modules-load.service
Before=musicplayer.service

[Service]
Type=oneshot
User=user
ExecStart=/home/user/oled_test_env/bin/python3 /home/user/src/splash.py boot
RemainAfterExit=yes

[Install]
WantedBy=sysinit.target
⚠️ Development Rules & Guardrails
Never Re-Claim GPIO 22: The Linux kernel locks this for gpio-shutdown. Any instance of Button(22) inside Python will trigger an lgpio.error: 'GPIO busy' crash.
Pygame Audio Routing: Pygame must initialization without forcing an ALSA audio driver lock (os.environ["SDL_AUDIODRIVER"] = "alsa" is banned). It must naturally utilize the PipeWire user runtime variables injected by systemd.
Screen Management on Exit: The main player.py must not call display.clear() in its finally block during shutdown, allowing the splash.py execution to smoothly overwrite the buffer with the termination warning message without intermediate flickering.