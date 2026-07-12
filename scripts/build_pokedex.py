import requests
import json
import os
import time
from PIL import Image
from io import BytesIO

# Set up the directories
CACHE_DIR = "pokedex_cache"
SPRITES_DIR = os.path.join(CACHE_DIR, "sprites")
os.makedirs(SPRITES_DIR, exist_ok=True)

pokedex_db = {}

print("Building Pokédex cache... This will take a couple of minutes.")

for pokemon_id in range(1, 152):
    print(f"Fetching #{pokemon_id}...")
    
    # 1. Fetch JSON data
    url = f"https://pokeapi.co/api/v2/pokemon/{pokemon_id}"
    response = requests.get(url)
    
    if response.status_code != 200:
        print(f"Failed to fetch {pokemon_id}")
        continue
        
    data = response.json()
    
    # 2. Extract the specific stats we want
    # PokeAPI heights are in decimetres, weights are in hectograms
    pokedex_db[str(pokemon_id)] = {
        "name": data['name'].capitalize(),
        "height_m": data['height'] / 10.0, 
        "weight_kg": data['weight'] / 10.0,
        "type": [t['type']['name'].capitalize() for t in data['types']]
    }
    
    # 3. Download and pre-process the Red/Blue sprite
    sprite_url = data['sprites']['versions']['generation-i']['red-blue']['front_default']
    if sprite_url:
        img_response = requests.get(sprite_url)
        img = Image.open(BytesIO(img_response.content))
        
        # Convert to 1-bit monochrome right now to save Pi CPU later
        img_1bit = img.convert("1")
        
        # Save as a standard PNG
        sprite_path = os.path.join(SPRITES_DIR, f"{pokemon_id}.png")
        img_1bit.save(sprite_path)
    
    # Be polite to the free API
    time.sleep(0.25)

# 4. Save the compiled text data to a single JSON file
db_path = os.path.join(CACHE_DIR, "pokedex.json")
with open(db_path, "w") as f:
    json.dump(pokedex_db, f, indent=4)

print("Done! You can now move the 'pokedex_cache' folder to your Pi.")