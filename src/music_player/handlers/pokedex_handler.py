"""
Pokédex Handler
Displays Pokémon sprite and stats on OLED display when a Pokédex tag is scanned.
Alternates between full-screen sprite and text stats.
"""

import time
from PIL import Image, ImageDraw, ImageFont, ImageOps
from music_player.handlers.base_handler import BaseHandler

try:
    from music_player.pokedex_cache import get_pokemon, get_random_pokemon
except ImportError:
    get_pokemon = None
    get_random_pokemon = None


class PokedexHandler(BaseHandler):
    """Display Pokémon data and sprite from catalog entry on the OLED display."""

    def __init__(self):
        self._pokemon_data = None
        self._pokemon_sprite = None
        self._inverted_sprite = None
        self._pokemon_id = None
        self._font = self._load_font()

    def play(self, assets, state, hardware_dict):
        """Load Pokémon data and display it."""
        if get_pokemon is None:
            print("[-] Pokédex cache module not available")
            state.current_playing = False
            return

        # Get Pokémon ID from assets
        pokemon_id = assets.get("pokemon_id")
        if not pokemon_id:
            state.current_playing = False
            return

        # Load Pokémon data
        if pokemon_id == "random":
            self._pokemon_data, self._pokemon_sprite = get_random_pokemon()
        else:
            try:
                pokemon_id = int(pokemon_id)
                self._pokemon_data, self._pokemon_sprite = get_pokemon(pokemon_id)
            except (ValueError, TypeError):
                print(f"[-] Invalid Pokémon ID: {pokemon_id}")
                state.current_playing = False
                return

        if self._pokemon_data is None or self._pokemon_sprite is None:
            print(f"[-] Failed to load Pokémon #{pokemon_id}")
            state.current_playing = False
            return

        self._pokemon_id = self._pokemon_data.get("id")
        print(f"[+] Pokédex: {self._pokemon_data.get('name')} (#{self._pokemon_id})")
        
        # Pre-invert the sprite here so we don't waste CPU cycles doing it every frame
        self._inverted_sprite = ImageOps.invert(self._pokemon_sprite.convert('L')).convert('1')
        
        # Display the Pokémon
        self._display_pokemon(state, hardware_dict)
        state.current_playing = True

    def update(self, state, hardware_dict):
        """Refresh the display every frame while tag is present."""
        if not getattr(state, "current_playing", False):
            return
        
        if self._pokemon_data is None or self._inverted_sprite is None:
            return

        self._display_pokemon(state, hardware_dict)

    def stop(self, state, hardware_dict):
        """Cleanup resources."""
        state.current_playing = False
        self._pokemon_data = None
        self._pokemon_sprite = None
        self._inverted_sprite = None
        self._pokemon_id = None

    def _load_font(self):
        """Load Pokemon Classic font with fallback to default font."""
        import os
        
        # Try multiple possible paths
        font_paths = [
            "/opt/music-player/fonts/Pokemon Classic.ttf",  # Deployed on Pi
            "fonts/Pokemon Classic.ttf",                     # Development (from project root)
            os.path.expanduser("~/src/axehead_fm/fonts/Pokemon Classic.ttf"),  # Dev fallback
        ]
        
        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    # Load with size 14 for labels
                    return ImageFont.truetype(font_path, size=6)
                except Exception as e:
                    print(f"[-] Failed to load font from {font_path}: {e}")
        
        # Fallback to default font
        print("[!] Pokemon Classic font not found, using default font")
        return ImageFont.load_default()

    def _display_pokemon(self, state, hardware_dict):
        """Render the alternating Pokémon sprite and metadata on the OLED."""
        display = hardware_dict.get("display")
        if display is None or not hasattr(display, "display"):
            return

        try:
            # Create a clean 128x64 black canvas
            canvas = Image.new("1", (128, 64), 0)
            draw = ImageDraw.Draw(canvas)
            
            # Determine which state to show based on the system clock.
            # int(time.time() / 3) increments every 3 seconds.
            # % 2 alternates between 0 and 1.
            show_image = int(time.time() / 3) % 2 == 0

            if show_image:
                # --- STATE A: The Image ---
                # Center the sprite dynamically (handles 56x56 or 64x64)
                x_offset = (128 - self._inverted_sprite.width) // 2
                y_offset = (64 - self._inverted_sprite.height) // 2
                canvas.paste(self._inverted_sprite, (x_offset, y_offset))
                
                # Put the ID in the top left corner as a nice overlay
                draw.text((0, 0), f"#{self._pokemon_id}", fill=1, font=self._font)

            else:
                # --- STATE B: The Stats ---
                name = self._pokemon_data.get("name", "Unknown")
                types = self._pokemon_data.get("types", [])
                
                # Convert back to standard units
                height_m = self._pokemon_data.get("height", 0) / 10.0
                weight_kg = self._pokemon_data.get("weight", 0) / 10.0
                
                # Format text
                name_str = f"{name} #{self._pokemon_id}"
                type_str = f"Type: {', '.join(types)}"
                height_str = f"HT: {height_m}m"
                weight_str = f"WT: {weight_kg}kg"
                
                # Draw text lines spaced cleanly apart
                draw.text((0, 2), name_str.upper(), fill=1, font=self._font)
                draw.text((0, 16), type_str.upper(), fill=1, font=self._font)
                draw.text((0, 30), height_str.upper(), fill=1, font=self._font)
                draw.text((0, 44), weight_str.upper(), fill=1, font=self._font)

            # Push to the SH1106
            display.display(canvas)
            
        except Exception as exc:
            print(f"[-] Failed to render Pokédex display: {exc}")