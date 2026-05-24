# 📻 Raspberry Pi Music & Video Player (axehead_fm)

An idempotent, high-performance physical music and video player built for the Raspberry Pi. This system features **NFC Token-based music and video playback**, custom high-speed monochrome OLED graphics, Bluetooth audio routing, and ultra-fast, dithered video streaming.

---

## 🚀 Key Features
* **NFC-Based Playback:** Placing an NFC tag on the scanner instantly triggers a song or video corresponding to the token. Removing the tag halts the media.
* **Preprocessed 1-Bit Video Stream:** High-resolution videos are compiled into custom `.bin` files with beautifully detailed Floyd-Steinberg error-diffusion dithering.
* **Instant Start Loader:** Deferred/lazy Python imports and an optimized lightweight cassette animation thread allow the screen to light up in **under 50 milliseconds** while heavy dependencies load in the background.
* **Zero-Latency Audio Sync:** Video playback is dynamically bound to a high-precision hardware audio clock buffer via Pygame Mixer, guaranteeing perfect lip-sync.
* **Smooth Bluetooth Routing:** Clean UI menu for discovering, connecting, and disconnecting Bluetooth headphones or speakers.
* **Reliable Graceful Shutdowns:** Multi-threaded signal handling intercepts termination signals immediately for instantaneous systemd restarts and clean resource releases.

---

## 🛠️ Installation & Setup

This repository contains an idempotent `install.sh` script that automates the installation of system dependencies, builds python virtual environments, sets hardware configurations (such as raising the I2C speed to **400kHz**), and installs systemd background services.

```bash
# Clone the repository
git clone git@github.com:YOUR_USERNAME/axehead_fm.git
cd axehead_fm

# Run the installer as root
sudo ./install.sh
```

---

## 📂 Project Structure
```text
axehead_fm/
├── catalog.json              # Media database associating NFC tokens with audio/video paths
├── install.sh                # Automated system configuration and service installer
├── pyproject.toml            # Python package configurations & dependencies
├── nfc_diagnostics.py        # Independent tool for scanning NFC card raw byte block sectors
├── scripts/
│   └── preprocess_video.py   # Script to convert standard MP4s to high-quality 1-bit .bin streams
├── src/
│   └── music_player/
│       ├── __init__.py       # Package definition
│       ├── player.py         # Main physical music player daemon
│       ├── video_player.py   # Ultra-fast dithered video and audio renderer
│       ├── bluetooth_manager.py # Robust DBus-based Bluetooth discovery & router
│       ├── splash.py         # Boot and shutdown screen rendering
│       └── image_test.py     # Independent display rendering test utility
└── systemd/                  # Configuration files for music-player and music-splash services
```

---

## 📺 How to Play Videos & Audio

### 1. Preprocess your video
Before playing, run the preprocessor to convert any standard MP4 into an optimized 1-bit video binary:
```bash
/opt/music-player/venv/bin/python3 scripts/preprocess_video.py input_video.mp4 output_video.bin
```

### 2. Extract the high-quality audio
Extract the audio from the `.mp4` into a matching `.mp3` with the exact same base name in the same folder:
```bash
ffmpeg -i input_video.mp4 -q:a 0 -map a output_video.mp3
```

### 3. Play the video on the OLED screen
Run the player using the virtual environment:
```bash
/opt/music-player/venv/bin/python3 src/music_player/video_player.py output_video.bin
```

---

## 🐙 GitHub Integration Guide

If you are hosting this project on GitHub and developing directly on your Raspberry Pi, follow these instructions to set up authentication and manage your code safely.

### 1. Generating an SSH Key on the Raspberry Pi
Using SSH keys is the most secure and reliable way to push and pull your changes to/from GitHub without typing your password each time.

Generate a new secure ED25519 SSH key:
```bash
ssh-keygen -t ed25519 -C "your_email@example.com"
```
*Press Enter to accept the default file location, and optional: enter a secure passphrase.*

### 2. Registering your SSH Key with GitHub
Start the SSH agent in the background:
```bash
eval "$(ssh-agent -s)"
```

Add your newly generated private key to the agent:
```bash
ssh-add ~/.ssh/id_ed25519
```

Output the public key to your terminal:
```bash
cat ~/.ssh/id_ed25519.pub
```

Copy the entire output starting with `ssh-ed25519`.
1. Go to **GitHub.com** -> Click your Profile Picture -> **Settings**.
2. On the left sidebar, click **SSH and GPG keys**.
3. Click the green **New SSH key** button.
4. Give it a descriptive Title (e.g., `Raspberry Pi Player`) and paste your public key in the **Key** field.
5. Click **Add SSH key**.

Verify your connection:
```bash
ssh -T git@github.com
# You should see: Hi USERNAME! You've successfully authenticated...
```

### 3. Managing the Git Repository (Common Commands)

To initialize, commit, and push your changes to your repository:

```bash
# If initializing for the first time
git init
git checkout -b develop
git remote add origin git@github.com:YOUR_USERNAME/axehead_fm.git

# Stage and commit your changes
git add .
git commit -m "Optimize video player with retro loading screen and 8KB audio buffer"

# Push your changes to the develop branch
git push -u origin develop
```

To update your Raspberry Pi with the latest changes made on another machine:
```bash
git pull origin develop
```
