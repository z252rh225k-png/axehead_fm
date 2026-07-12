"""
Hardware initialization utilities.
Handles waiting for audio devices and other hardware startup checks.
"""

import time
import subprocess
import logging
import threading

logger = logging.getLogger(__name__)


def wait_for_audio_hardware(callback=None, timeout=30, poll_interval=2):
    """
    Wait for USB audio hardware to be detected via ALSA in background.
    
    Designed to run in a daemon thread so main application doesn't block.
    
    Args:
        callback: Optional function to call when hardware is detected
        timeout: Maximum time to wait in seconds (0 = infinite)
        poll_interval: Time between checks in seconds
    
    Returns:
        True if USB audio detected, False if timeout exceeded
    """
    logger.info("🔊 Starting USB Audio hardware detection (background thread)...")
    
    elapsed = 0
    detected = False
    
    while True:
        try:
            result = subprocess.run(
                ['aplay', '-l'],
                capture_output=True,
                text=True,
                timeout=3
            )
            
            if "USB" in result.stdout or "USB Audio" in result.stdout:
                logger.info("✓ USB audio hardware detected!")
                detected = True
                
                if callback:
                    try:
                        logger.debug("Calling audio initialization callback...")
                        callback()
                    except Exception as e:
                        logger.error(f"Error in audio initialization callback: {e}")
                
                return True
            
            if timeout > 0 and elapsed >= timeout:
                logger.warning(f"⚠ USB audio not detected after {timeout}s - audio initialization skipped")
                return False
            
            logger.debug(f"Audio hardware not ready, retrying in {poll_interval}s (elapsed: {elapsed}s/{timeout}s)...")
            time.sleep(poll_interval)
            elapsed += poll_interval
            
        except subprocess.TimeoutExpired:
            logger.debug("aplay command timeout, retrying...")
            if timeout > 0 and elapsed >= timeout:
                logger.warning(f"⚠ USB audio detection timed out after {timeout}s")
                return False
            time.sleep(poll_interval)
            elapsed += poll_interval
            
        except FileNotFoundError:
            logger.error("aplay command not found. ALSA tools not installed.")
            return False
            
        except Exception as e:
            logger.error(f"Error checking audio hardware: {e}")
            if timeout > 0 and elapsed >= timeout:
                return False
            time.sleep(poll_interval)
            elapsed += poll_interval


def start_audio_detection_thread(callback=None, timeout=30):
    """
    Start audio hardware detection as a background daemon thread.
    Non-blocking - main application continues immediately.
    
    Args:
        callback: Optional function to call when hardware is detected
        timeout: Maximum time to wait in seconds
    
    Returns:
        threading.Thread object
    """
    thread = threading.Thread(
        target=wait_for_audio_hardware,
        args=(callback, timeout),
        daemon=True,
        name="AudioHardwareDetection"
    )
    thread.start()
    logger.info("Audio detection thread started (daemon mode)")
    return thread
