Yes, RTÉ provides direct streaming URLs that you can easily plug into a Python script on your Raspberry Pi.
Since RTÉ broadcasts over a few different protocols, you have two primary URL options depending on what your code is set up to handle:
HLS Stream (Best Quality/Most Reliable): [https://www.rte.ie/manifests/lyric.m3u8](https://www.rte.ie/manifests/lyric.m3u8)
Icecast Stream: [http://icecast2.rte.ie/lyric](http://icecast2.rte.ie/lyric)
How to play it via Python on a Raspberry Pi
Decoding live internet radio streams (especially modern HLS/AAC streams) natively in Python can be incredibly complex. The most robust and easiest way to do this on a Raspberry Pi is to use the python-vlc library, which acts as a wrapper around the standard VLC media player. It handles all the buffering, decoding, and audio output routing for you.
Step 1: Install Dependencies
First, ensure you have the VLC engine installed on your Pi, and then install the Python bindings. Open your terminal and run:
Bash
sudo apt update
sudo apt install vlc
pip install python-vlc
Step 2: The Python Code
Here is a simple, lightweight script to stream Lyric FM.
Python
import vlc
import time

# RTÉ Lyric FM HLS stream URL
STREAM_URL = "https://www.rte.ie/manifests/lyric.m3u8"

def play_radio():
    print("Connecting to RTÉ Lyric FM...")
    
    # Create the VLC instance and player
    instance = vlc.Instance('--novideo') # Optional: prevents UI popups if you are in a desktop environment
    player = instance.media_player_new()
    media = instance.media_new(STREAM_URL)
    
    player.set_media(media)
    player.play()
    
    print("Playing! Press Ctrl+C to stop.")
    
    # Keep the script running while the music plays
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping stream...")
        player.stop()

if __name__ == "__main__":
    play_radio()
A quick tip for the Pi: If you aren't hearing any audio, your Raspberry Pi might be sending the sound to the HDMI port instead of the 3.5mm headphone jack. You can force the audio output through the audio jack by running raspi-config in your terminal, navigating to System Options > Audio, and selecting the headphone jack.