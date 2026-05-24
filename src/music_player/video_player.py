import sys
import os
import time
import subprocess

# Let's defer cv2 and numpy to speed up initial script load to under 100ms!
# These two libraries alone take about 1.5 seconds to load on a Pi.
# We'll load them inside play_preprocessed_bin/play_video after the screen lights up.

# Luma OLED imports
from luma.core.interface.serial import i2c
from luma.oled.device import sh1106

def find_audio_player():
    """
    Scans the system for command-line media players capable of playing audio.
    Prioritizes lightweight ones available on Raspberry Pi OS.
    """
    players = ["mpv", "ffplay", "cvlc"]
    for p in players:
        # Check if utility is installed in system $PATH
        if subprocess.run(["which", p], capture_output=True).returncode == 0:
            return p
    return None

def start_audio_process(player, video_path):
    """
    Launches the chosen command-line player to extract and stream
    only the audio stream from the MP4 in a background process.
    """
    if not player:
        return None

    print(f"[+] Launching background audio player using '{player}'...")
    try:
        if player == "mpv":
            # --no-video disables rendering the video window
            return subprocess.Popen(
                ["mpv", "--no-video", video_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        elif player == "ffplay":
            # -nodisp runs ffplay in headless audio-only mode
            return subprocess.Popen(
                ["ffplay", "-nodisp", "-autoexit", video_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        elif player == "cvlc":
            # cvlc is headless VLC
            return subprocess.Popen(
                ["cvlc", "--no-video", "--play-and-exit", video_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
    except Exception as e:
        print(f"[-] Failed to launch background audio process: {e}")
    return None

def play_preprocessed_bin(bin_path):
    """
    Plays a preprocessed Raw 1-Bit (.bin) video file.
    Loads the entire 1-bit frame buffer into memory (or reads sequentially),
    keeping perfect sync with background audio using a Pygame-based High-Precision Master Clock.
    """
    if not os.path.exists(bin_path):
        print(f"[-] Error: Bin file not found: {bin_path}")
        return

    print(f"[+] Initializing OLED display...")
    try:
        serial_i2c = i2c(port=1, address=0x3C)
        display = sh1106(serial_i2c)
    except Exception as e:
        print(f"[-] Failed to initialize display: {e}")
        return

    # Retro loading screen animation thread
    # Renders a rotating retro cassette tape reels graphic instantly in a background thread 
    # while the main thread performs the heavy library imports and file buffering.
    loading_active = True
    def play_loading_animation():
        from luma.core.render import canvas
        import random
        frame_idx = 0
        
        # Use simple integer rotation approximation to avoid importing numpy inside the loader thread
        # This keeps the loader thread lightweight and completely dependency-free so it starts in 10ms!
        # Standard cassette spools have a simple cross spoke structure.
        # We can draw 4 lines representing 8 spokes that rotate.
        spoke_patterns = [
            # angle index 0
            [(0, 7), (7, 0), (0, -7), (-7, 0)],
            # angle index 1 (~30 deg)
            [(6, 3), (3, -6), (-6, -3), (-3, 6)],
            # angle index 2 (~60 deg)
            [(3, 6), (6, -3), (-3, -6), (-6, 3)]
        ]
        
        try:
            while loading_active:
                with canvas(display) as draw:
                    # 1. Title text
                    draw.text((12, 2), "LOADING CASSETTE...", fill="white")
                    draw.line((0, 14, 128, 14), fill="white")
                    
                    # 2. Outer cassette shell outline
                    draw.rectangle((24, 20, 104, 52), outline="white")
                    
                    # 3. Spinning Reels
                    left_reel_x, left_reel_y = 44, 36
                    right_reel_x, right_reel_y = 84, 36
                    reel_r = 7
                    draw.ellipse((left_reel_x - reel_r, left_reel_y - reel_r, left_reel_x + reel_r, left_reel_y + reel_r), outline="white")
                    draw.ellipse((right_reel_x - reel_r, right_reel_y - reel_r, right_reel_x + reel_r, right_reel_y + reel_r), outline="white")
                    
                    # Get precalculated spoke offsets
                    spokes = spoke_patterns[frame_idx % len(spoke_patterns)]
                    
                    # Left Reel lines
                    draw.line((left_reel_x + spokes[0][0], left_reel_y + spokes[0][1], left_reel_x + spokes[2][0], left_reel_y + spokes[2][1]), fill="white")
                    draw.line((left_reel_x + spokes[1][0], left_reel_y + spokes[1][1], left_reel_x + spokes[3][0], left_reel_y + spokes[3][1]), fill="white")
                    
                    # Right Reel lines
                    draw.line((right_reel_x + spokes[0][0], right_reel_y + spokes[0][1], right_reel_x + spokes[2][0], right_reel_y + spokes[2][1]), fill="white")
                    draw.line((right_reel_x + spokes[1][0], right_reel_y + spokes[1][1], right_reel_x + spokes[3][0], right_reel_y + spokes[3][1]), fill="white")
                    
                    # 4. Moving CRT Static tuning bar at the very bottom
                    for i in range(0, 128, 8):
                        h = random.randint(0, 3)
                        if h > 0:
                            draw.line((i, 64 - h, i + random.randint(1, 4), 64 - h), fill="white")
                            
                frame_idx += 1
                time.sleep(0.04) # ~25 FPS loader speed
        except Exception:
            pass # Keep silent if screen interrupts on shutdown/close

    # Start retro load animation thread immediately
    import threading
    anim_thread = threading.Thread(target=play_loading_animation, daemon=True)
    anim_thread.start()

    # Now we perform the deferred imports of heavy libraries (NumPy, OpenCV, Pillow, Pygame)
    # while the loading thread is ALREADY actively drawing to the screen!
    print(f"[+] Instantly launched loader! Importing heavy dependencies in background...")
    global np, cv2, Image, pygame
    import numpy as np_lib
    import cv2 as cv_lib
    from PIL import Image as PIL_Image
    import pygame as pg
    
    np = np_lib
    cv2 = cv_lib
    Image = PIL_Image
    pygame = pg

    print(f"[+] Loading preprocessed video from: {bin_path}")
    
    # Read file and header information
    try:
        with open(bin_path, 'rb') as f:
            magic = f.read(4)
            if magic != b'R1B\x01':
                print("[-] Warning: File magic bytes do not match expected 'R1B\\x01' format. Attempting playback anyway...")
                # If magic didn't match, we wind back
                f.seek(0)
                fps = 24.0
                # Rough estimate of frames
                total_frames = int((os.path.getsize(bin_path)) / 1024)
            else:
                fps = np.frombuffer(f.read(4), dtype=np.float32)[0]
                total_frames = int(np.frombuffer(f.read(4), dtype=np.uint32)[0])

            print(f"[+] Loader parsed: {fps:.2f} FPS | {total_frames} total frames")
            
            # Load all frames to RAM to eliminate SD card latency
            print("[*] Loading frame buffer into RAM...")
            frames = []
            for _ in range(total_frames):
                buf = f.read(1024)
                if len(buf) < 1024:
                    break
                # Convert 1024 raw bytes directly back to a 1-bit PIL image object
                frames.append(Image.frombytes("1", (128, 64), buf))
            
            actual_total_frames = len(frames)
            print(f"[+] Buffered {actual_total_frames} frames in memory successfully.")
    finally:
        # Guarantee the loading thread stops when frame loading finishes
        loading_active = False
        anim_thread.join(timeout=0.5)

    if actual_total_frames == 0:
        print("[-] Error: No video frames could be loaded.")
        return

    frame_delay = 1.0 / fps

    # Find and spawn background audio stream
    base_path, _ = os.path.splitext(bin_path)
    audio_source = None
    for ext in [".mp3", ".wav", ".ogg", ".mp4"]:
        candidate = base_path + ext
        if os.path.exists(candidate):
            audio_source = candidate
            break

    use_pygame_audio = False
    audio_process = None

    if audio_source:
        _, audio_ext = os.path.splitext(audio_source)
        if audio_ext.lower() == '.mp4':
            audio_player = find_audio_player()
            if audio_player:
                audio_process = start_audio_process(audio_player, audio_source)
            else:
                print("[-] WARNING: No background player found to play MP4 audio stream!")
        else:
            # Load and play audio via Pygame Mixer for zero startup latency and precision sync
            print(f"[+] Initializing Pygame Mixer with optimized buffer for zero-latency, crackle-free playback...")
            try:
                if not pygame.mixer.get_init():
                    # Set frequency, size, stereo channels, and a massive buffer size (8192) to prevent underflow on Pi
                    pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=8192)
                    pygame.mixer.init()
            except Exception as e:
                print(f"[-] Pre-init failed: {e}. Falling back to default init...")
                if not pygame.mixer.get_init():
                    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=8192)
            try:
                pygame.mixer.music.load(audio_source)
                pygame.mixer.music.play()
                use_pygame_audio = True
                print(f"[+] Playing audio stream via Pygame Mixer: {audio_source}")
            except Exception as e:
                print(f"[-] Failed to play audio using Pygame Mixer: {e}. Falling back to background subprocess...")
                audio_player = find_audio_player()
                if audio_player:
                    audio_process = start_audio_process(audio_player, audio_source)
    else:
        print("[-] WARNING: No matching audio file found with the same name. Running video in silent mode!")

    print("[*] Streaming video to OLED. Press Ctrl+C in terminal to stop.")

    # Performance monitoring variables
    frame_count = 0
    skipped_frames = 0
    fps_start_time = time.time()
    last_report_time = time.time()

    # Master Clock Sync variables
    video_start_time = time.time()
    
    # If using external background subprocess, wait 0.4 seconds to let the binary load and start audio stream
    if audio_process:
        time.sleep(0.4)
        video_start_time = time.time()

    try:
        while True:
            # Calculate where the video should be based on actual elapsed time (Master Clock)
            if use_pygame_audio:
                music_pos_ms = pygame.mixer.music.get_pos()
                if music_pos_ms < 0:
                    # Pygame music ended or hasn't started, default to system clock
                    elapsed_time = time.time() - video_start_time
                else:
                    elapsed_time = music_pos_ms / 1000.0
            else:
                elapsed_time = time.time() - video_start_time

            target_frame_idx = int(elapsed_time * fps)

            # End of video logic
            if target_frame_idx >= actual_total_frames:
                print("[+] Video playback complete.")
                break

            # Draw the frame requested by the master clock
            pil_img = frames[target_frame_idx]

            # Measure Hardware I2C Render time
            render_start = time.time()
            display.display(pil_img)
            render_time = time.time() - render_start
            frame_count += 1

            # Sleep briefly only if we are ahead of schedule
            expected_frame_idx = target_frame_idx + 1
            next_frame_target_time = expected_frame_idx * frame_delay
            sleep_time = float(next_frame_target_time - elapsed_time)
            if sleep_time > 0:
                time.sleep(sleep_time)

            # Print stats every 2 seconds
            now = time.time()
            if now - last_report_time >= 2.0:
                duration = now - fps_start_time
                actual_fps = frame_count / duration
                print(
                    f"[Diag] Render FPS: {actual_fps:.1f} | "
                    f"Time: {elapsed_time:.1f}s | "
                    f"Decode: 0.0ms | "
                    f"Dither: 0.0ms | "
                    f"I2C Draw: {render_time*1000:.1f}ms"
                )

                # Reset counters
                frame_count = 0
                fps_start_time = now
                last_report_time = now

    except KeyboardInterrupt:
        print("\n[+] Video playback interrupted by user.")
    finally:
        if use_pygame_audio:
            pygame.mixer.music.stop()
        if audio_process:
            print("[+] Stopping background audio player process...")
            audio_process.terminate()
            audio_process.wait()
        print("[+] Video resources released.")

def play_video(video_path):
    """
    Decodes an MP4 file using OpenCV, applies optimized dithering,
    scales to 128x64, and streams it to the SH1106 OLED screen in real-time.
    Uses Master-Clock synchronization (frame skipping) to keep video perfectly synced
    with background audio, and replaces Pillow dithering with ultra-fast NumPy Bayer dithering.
    """
    # Lazy imports for the raw video playback branch as well
    global np, cv2, Image
    import numpy as np_lib
    import cv2 as cv_lib
    from PIL import Image as PIL_Image
    
    np = np_lib
    cv2 = cv_lib
    Image = PIL_Image

    # Detect if file is already a preprocessed binary file
    _, ext = os.path.splitext(video_path)
    if ext.lower() in ['.bin', '.r1b']:
        play_preprocessed_bin(video_path)
        return

    if not os.path.exists(video_path):
        print(f"[-] Error: Video file not found: {video_path}")
        return

    print(f"[+] Initializing OLED display...")
    try:
        serial_i2c = i2c(port=1, address=0x3C)
        display = sh1106(serial_i2c)
    except Exception as e:
        print(f"[-] Failed to initialize display: {e}")
        return

    print(f"[+] Loading video: {video_path}")
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print("[-] Error: OpenCV could not open the video file.")
        return

    # Extract video properties for synchronization
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0 or fps > 120:
        fps = 24.0 # Fallback
    frame_delay = 1.0 / fps

    print(f"[+] Video properties: {fps:.2f} FPS (Target Delay: {frame_delay*1000:.1f}ms per frame)")

    # Find and spawn background audio stream
    audio_player = find_audio_player()
    audio_process = None
    if audio_player:
        audio_process = start_audio_process(audio_player, video_path)
    else:
        print("[-] WARNING: No lightweight command-line audio player (mpv, ffplay, or cvlc) was found!")
    print("[*] Streaming video to OLED. Press Ctrl+C in terminal to stop.")

    # FPS and Sync Diagnostics
    frame_count = 0
    skipped_frames = 0
    fps_start_time = time.time()
    last_report_time = time.time()
        
    # Pre-calculated 4x4 Bayer Ordered Dithering Matrix for ultra-fast NumPy 1-bit rendering
    # This emulates grayscale gradients cleanly without Pillow's slow 48ms loops.
    bayer_matrix = (np.array([
        [ 0,  8,  2, 10],
        [12,  4, 14,  6],
        [ 3, 11,  1,  9],
        [15,  7, 13,  5]
    ], dtype=np.float32) * (255.0 / 16.0))

    # Replicate the bayer pattern to cover the entire 128x64 frame area
    bayer_pattern = np.tile(bayer_matrix, (16, 32))

    # Master Clock Sync variables
    video_start_time = time.time()
    expected_frame_idx = 0

    try:
        while True:
            # Calculate where the video should be based on actual elapsed time (Master Clock)
            elapsed_time = time.time() - video_start_time
            target_frame_idx = int(elapsed_time * fps)

            # Frame skipping logic: Discard frames if we are lagging behind the master audio clock
            while expected_frame_idx < target_frame_idx:
                cap.grab() # grab() is extremely fast as it fetches the frame packet without decoding it!
                expected_frame_idx += 1
                skipped_frames += 1

            # Decode the next frame
            decode_start = time.time()
            ret, frame = cap.read()
            if not ret:
                print("[+] Video ended or loop complete.")
                break
            expected_frame_idx += 1
            decode_time = time.time() - decode_start

            # Processing Time: Optimized Bayer Dithering
            process_start = time.time()
            # 1. Grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            # 2. Resize to 128x64 using fast linear interpolation
            resized = cv2.resize(gray, (128, 64), interpolation=cv2.INTER_LINEAR)

            # 3. Bayer Dithering: compare pixel values to our Bayer threshold pattern
            # Optimized vector math in NumPy (takes <1.5ms instead of Pillow's 48ms!)
            dithered = (resized > bayer_pattern).astype(np.uint8) * 255

            # Convert NumPy array directly back to 1-bit Pillow image
            pil_img = Image.fromarray(dithered).convert("1")
            process_time = time.time() - process_start

            # Measure Hardware I2C Render time
            render_start = time.time()
            display.display(pil_img)
            render_time = time.time() - render_start
            frame_count += 1

            # Sleep briefly only if we are ahead of schedule
            elapsed = time.time() - video_start_time
            next_frame_target_time = expected_frame_idx * frame_delay
            sleep_time = next_frame_target_time - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
            # Print stats every 2 seconds
            now = time.time()
            if now - last_report_time >= 2.0:
                duration = now - fps_start_time
                actual_fps = frame_count / duration
                total_attempted = frame_count + skipped_frames
                skip_rate = (skipped_frames / total_attempted * 100) if total_attempted > 0 else 0
                print(
                    f"[Diag] Render FPS: {actual_fps:.1f} | "
                    f"Skipped: {skip_rate:.1f}% | "
                    f"Decode: {decode_time*1000:.1f}ms | "
                    f"Bayer-Dither: {process_time*1000:.1f}ms | "
                    f"I2C Draw: {render_time*1000:.1f}ms"
                )

                # Reset counters
                frame_count = 0
                skipped_frames = 0
                fps_start_time = now
                last_report_time = now

    except KeyboardInterrupt:
        print("\n[+] Video playback interrupted by user.")
    finally:
        cap.release()
        # Cleanly stop the background audio player process if running
        if audio_process:
            print("[+] Stopping background audio player process...")
            audio_process.terminate()
            audio_process.wait()
        print("[+] Video resources released.")

def main():
    # If no path is provided, attempt to run your default test video
    default_test_file = "/home/user/src/axehead_fm/Rick Astley - Never Gonna Give You Up (Official Video) (4K Remaster) [dQw4w9WgXcQ].mp4"
    
    video_path = sys.argv[1] if len(sys.argv) > 1 else default_test_file
    play_video(video_path)

if __name__ == "__main__":
    main()

