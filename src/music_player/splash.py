import sys
import time
import math
import subprocess
from music_player.hardware.display import Display


def draw_loading_spinner(draw, frame):
    """Draw a rotating loading spinner.
    
    Args:
        draw: PIL ImageDraw object
        frame: Animation frame (0-7)
    """
    # Center of display
    cx, cy = 64, 32
    radius = 12
    
    # Draw a rotating spinner with 8 frames
    # Each frame has lines radiating from center, rotating 45 degrees
    spokes = 8
    for i in range(spokes):
        angle = (i + frame) * (360 / spokes) / 180.0 * 3.14159  # Convert to radians
        
        # Calculate spoke endpoints
        x1 = cx + int(math.cos(angle) * (radius - 4))
        y1 = cy + int(math.sin(angle) * (radius - 4))
        x2 = cx + int(math.cos(angle) * radius)
        y2 = cy + int(math.sin(angle) * radius)
        
        # Draw line
        draw.line([(x1, y1), (x2, y2)], fill=1, width=1)


def is_player_ready():
    """Check if the music player service is active and ready."""
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "music-player"],
            capture_output=True,
            timeout=1
        )
        return result.returncode == 0
    except Exception:
        return False


def display_boot_message():
    """Display animated loading spinner on boot, continuously until player is ready."""
    display = Display()
    
    # Prevent Luma from wiping the screen when the script exits
    if display.device:
        display.device.cleanup = lambda: None
    
    frame = 0
    start_time = time.time()
    frame_delay = 0.1  # 100ms per frame = ~10 FPS smooth animation
    last_check_time = 0
    
    print("[+] Splash screen: Starting animated boot loader...")
    
    try:
        while True:
            # Check if player is ready (once per second to avoid overhead)
            current_time = time.time()
            if current_time - last_check_time >= 1.0:
                if is_player_ready():
                    print("[+] Splash screen: Player service detected, exiting gracefully...")
                    time.sleep(0.2)  # Brief delay to let player render first frame
                    break
                last_check_time = current_time
            
            # Draw current frame
            try:
                with display.canvas() as draw:
                    draw_loading_spinner(draw, frame % 8)
            except Exception as e:
                print(f"[!] Failed to draw loading spinner: {e}")
                break
            
            # Advance frame and wait
            frame += 1
            time.sleep(frame_delay)
            
            # Safety timeout: exit after 60 seconds regardless
            if current_time - start_time > 60:
                print("[!] Splash screen timeout after 60 seconds")
                break
    
    except KeyboardInterrupt:
        print("[+] Splash screen interrupted")
    except Exception as e:
        print(f"[!] Splash screen error: {e}")


def display_shutdown_message():
    """Display shutdown message on OLED screen."""
    display = Display()
    
    # Prevent Luma from wiping the screen when the script exits
    if display.device:
        display.device.cleanup = lambda: None
    try:
        with display.canvas() as draw:
            # Draw a simple X or stop symbol
            draw.line([(20, 20), (44, 44)], fill=1, width=2)
            draw.line([(44, 20), (20, 44)], fill=1, width=2)
    except Exception as e:
        print(f"[!] Failed to display shutdown message: {e}")


def main():
    """Main entry point for splash screen.
    
    Usage:
        music-splash          # Show boot loading animation
        music-splash stop     # Show shutdown symbol
    """
    if len(sys.argv) > 1 and "stop" in sys.argv:
        display_shutdown_message()
    else:
        display_boot_message()


if __name__ == "__main__":
    main()



