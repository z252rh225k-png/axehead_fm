import os
import re
import socket
from PIL import Image
from music_player.catalog.loader import load_catalog


def _resolve_text_template(text):
    """Expand simple template placeholders for dynamic QR and token content."""
    if not text:
        return text

    hostname = socket.gethostname()
    port = os.environ.get("AXEHEAD_PORT", "5000")
    replacements = {
        "${hostname}": hostname,
        "${host}": hostname,
        "${port}": port,
    }
    resolved = text
    for placeholder, value in replacements.items():
        resolved = resolved.replace(placeholder, value)
    return resolved

def extract_tag_payload(nfc_reader):
    """
    Reads the raw blocks of the NTAG sticker and searches for:
    1. A Pokédex ID (e.g. "poke_010", "poke_ball" for random)
    2. A song database ID key (e.g. "song_01", "song_02")
    3. A legacy Linux absolute file path ending in .mp3
    """
    raw_data = bytearray()
    try:
        for i in range(4, 20):
            block = nfc_reader.ntag2xx_read_block(i)
            if block:
                raw_data.extend(block)
    except Exception as e:
        print("Read error:", e)
        return None

    # Decode bytes ignoring messy NDEF header characters
    text = raw_data.decode('ascii', errors='ignore')
    
    # Check for Pokédex tags (poke_XXX format)
    match_poke = re.search(r'(poke_\w+)', text, re.IGNORECASE)
    if match_poke:
        return match_poke.group(1).lower()
    
    # Check catalog.json keys directly against raw text to bypass overlapping writes!
    catalog = load_catalog()
    for key in catalog.keys():
        if key in text:
            return key

    # Legacy regex lookup fallback for absolute paths
    match_path = re.search(r'(/home/.*?\.mp3)', text)
    if match_path:
        return match_path.group(1)
        
    return None

def resolve_playback_assets(payload):
    """
    Takes a tag payload and returns a dictionary with all metadata, including
    'audio', 'title', 'type', and 'artwork' (pre-rendered PIL image).
    
    Supports:
    - Pokédex tags: poke_XXX (e.g., poke_025, poke_ball, poke_random)
      Dynamically generates assets without needing catalog entries
    - Catalog entries: from catalog.json
    - Legacy paths: /home/.../*.mp3
    """
    catalog = load_catalog()
    
    # Handle Pokédex tags (poke_XXX) - generate assets dynamically
    if payload and isinstance(payload, str) and payload.lower().startswith("poke_"):
        poke_id = payload[5:]  # Remove "poke_" prefix
        
        # Resolve poke_ball or poke_random to "random" for handler
        if poke_id.lower() in ("ball", "random"):
            title = "Random Pokémon"
            pokemon_id = "random"
        else:
            # Extract numeric ID
            try:
                numeric_id = int(poke_id)
                title = f"Pokémon #{numeric_id}"
                pokemon_id = numeric_id
            except ValueError:
                # Invalid format, return None
                return None
        
        return {
            "type": "pokedex",
            "pokemon_id": pokemon_id,
            "title": title,
            "audio": "",
            "artwork": None
        }
    
    # Try database match
    if payload in catalog:
        entry = catalog[payload].copy()
        audio_path = entry.get("audio", "")
        title = entry.get("title", payload)
        image_path = entry.get("image", "")
        media_type = entry.get("type", "audio")
        
        # Load and pre-process artwork image
        artwork_img = None
        if image_path and os.path.exists(image_path):
            try:
                img = Image.open(image_path)
                # Resize to fit the exact OLED screen boundaries dynamically
                if img.size != (128, 64):
                    img = img.resize((128, 64), Image.Resampling.NEAREST)
                artwork_img = img.convert("1")
                print(f"[+] Loaded and processed artwork: {image_path}")
            except Exception as e:
                print(f"[-] Failed to process artwork image {image_path}: {e}")
                
        if media_type == "qr":
            entry["text"] = _resolve_text_template(entry.get("text", ""))
        entry["audio"] = audio_path
        entry["title"] = title
        entry["type"] = media_type
        entry["artwork"] = artwork_img
        return entry
    
    # Legacy direct file path support
    if payload and payload.endswith(".mp3"):
        title = os.path.basename(payload).replace(".mp3", "").replace("_", " ").title()
        return {
            "type": "audio",
            "audio": payload,
            "title": title,
            "artwork": None
        }

    return None
