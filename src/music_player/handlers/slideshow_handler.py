import os
import time
from PIL import Image
from music_player.handlers.base_handler import BaseHandler
from music_player.catalog.resolver import resolve_playback_assets

def load_slideshow_images(folder_path):
    """Loads all image files from a folder and converts them to 1-bit monochrome."""
    images = []
    if not folder_path or not os.path.exists(folder_path):
        return images
    try:
        files = sorted(os.listdir(folder_path))
        for f in files:
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                full_path = os.path.join(folder_path, f)
                try:
                    img = Image.open(full_path)
                    if img.size != (128, 64):
                        img = img.resize((128, 64), Image.Resampling.NEAREST)
                    images.append(img.convert("1"))
                except Exception as e:
                    print(f"[-] Failed to load slideshow image {full_path}: {e}")
    except Exception as e:
        print(f"[-] Error loading slideshow folder {folder_path}: {e}")
    return images


class SlideshowHandler(BaseHandler):
    def play(self, assets, state, hardware_dict):
        folder_path = assets.get("folder", "")
        audio_path = assets.get("audio", "")
        interval = float(assets.get("interval", 5.0))
        print(f"Slideshow active: {state.current_title} ({folder_path})")
        
        # Load images from directory
        state.slideshow_images = load_slideshow_images(folder_path)
        state.slideshow_index = 0
        state.next_slide_time = time.time() + interval
        
        audio_engine = hardware_dict["audio_engine"]
        if audio_path and os.path.exists(audio_path):
            audio_engine.load(audio_path)
            audio_engine.play(-1) # Loop forever
            
        state.current_playing = True

    def stop(self, state, hardware_dict):
        audio_engine = hardware_dict["audio_engine"]
        audio_engine.stop()
        state.slideshow_images = []
        state.current_playing = False

    def update(self, state, hardware_dict):
        if state.current_playing and state.slideshow_images:
            if time.time() >= state.next_slide_time:
                state.slideshow_index = (state.slideshow_index + 1) % len(state.slideshow_images)
                # Fetch current interval from metadata fallback
                if state.current_uid:
                    # Retrieve the catalog assets for current_uid or fallback to default interval
                    # Note: We can resolve metadata using the helper in resolver
                    assets = resolve_playback_assets(state.current_uid)
                    interval = float(assets.get("interval", 5.0)) if assets else 5.0
                else:
                    interval = 5.0
                state.next_slide_time = time.time() + interval
