"""
Pokédex Cache Manager
Pre-downloads and manages caching of Pokémon data and sprites from PokéAPI.
Supports caching Gen 1 (original 151) with 1-bit monochrome sprites.
Falls back to live API for newer generations.
"""

import os
import json
import random
import requests
from PIL import Image
from io import BytesIO


CACHE_DIR = "pokedex_assets"


def setup_cache():
    """Pre-downloads and caches the original 151 Pokemon if not already done."""
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)
        print(f"Creating cache directory at ./{CACHE_DIR}")

    print("Checking/Populating local Pokédex cache (1-151)...")
    for i in range(1, 152):
        json_path = os.path.join(CACHE_DIR, f"{i}.json")
        img_path = os.path.join(CACHE_DIR, f"{i}.png")

        # Skip if both files already exist
        if os.path.exists(json_path) and os.path.exists(img_path):
            continue

        print(f"Caching Gen 1: #{i}...")
        try:
            # Fetch from PokéAPI
            url = f"https://pokeapi.co/api/v2/pokemon/{i}"
            response = requests.get(url, timeout=10)
            data = response.json()

            # Extract just the metadata we need
            metadata = {
                "id": data["id"],
                "name": data["name"].capitalize(),
                "height": data["height"],  # decimeters
                "weight": data["weight"],  # hectograms
                "types": [t["type"]["name"].capitalize() for t in data["types"]]
            }

            # Fetch, convert, and save the 1-bit sprite
            sprite_url = data['sprites']['versions']['generation-i']['red-blue']['front_default']
            img_response = requests.get(sprite_url, timeout=10)
            img = Image.open(BytesIO(img_response.content))
            
            # Convert to 1-bit monochrome (black and white)
            img_1bit = img.convert("1")

            # Save files locally
            with open(json_path, "w") as f:
                json.dump(metadata, f, indent=4)
            img_1bit.save(img_path)

        except Exception as e:
            print(f"Failed to cache #{i}: {e}")
            
    print("Cache setup complete!")


def get_pokemon(pokemon_id):
    """
    Retrieves Pokemon data and sprite. 
    Checks local cache first; falls back to live web request for IDs > 151.
    
    Args:
        pokemon_id: Integer ID of the Pokémon to retrieve
        
    Returns:
        Tuple of (metadata_dict, PIL_Image) or (None, None) if failed
    """
    json_path = os.path.join(CACHE_DIR, f"{pokemon_id}.json")
    img_path = os.path.join(CACHE_DIR, f"{pokemon_id}.png")

    # 1. Try to load from local cache
    if os.path.exists(json_path) and os.path.exists(img_path):
        try:
            with open(json_path, "r") as f:
                metadata = json.load(f)
            sprite = Image.open(img_path)
            return metadata, sprite
        except Exception as e:
            print(f"[-] Error loading cached Pokémon #{pokemon_id}: {e}")

    # 2. Fallback to live API if not cached (or if ID > 151)
    print(f"#{pokemon_id} not in cache. Fetching live from PokéAPI...")
    try:
        url = f"https://pokeapi.co/api/v2/pokemon/{pokemon_id}"
        data = requests.get(url, timeout=10).json()

        metadata = {
            "id": data["id"],
            "name": data["name"].capitalize(),
            "height": data["height"],
            "weight": data["weight"],
            "types": [t["type"]["name"].capitalize() for t in data["types"]]
        }

        # Use standard default front sprite for newer generations
        sprite_url = data['sprites']['front_default']
        if not sprite_url:
            raise ValueError("No default sprite available for this Pokémon.")

        img_response = requests.get(sprite_url, timeout=10)
        img = Image.open(BytesIO(img_response.content))
        
        # Resize if necessary (newer sprites are 96x96, Gen 1 was 56x56)
        # 56x56 or 64x64 leaves nice framing on a 128x64 OLED
        if img.size != (56, 56):
            img = img.resize((56, 56), Image.Resampling.NEAREST)
        sprite = img.convert("1")

        # Optional: You could save this to the cache directory here 
        # so subsequent scans of this specific higher-gen Pokémon are also instant.
        
        return metadata, sprite

    except Exception as e:
        print(f"Error fetching live data for #{pokemon_id}: {e}")
        return None, None


def get_random_pokemon():
    """
    Returns a random Pokémon from Gen 1 (1-151).
    
    Returns:
        Tuple of (metadata_dict, PIL_Image) or (None, None) if failed
    """
    random_id = random.randint(1, 151)
    return get_pokemon(random_id)
