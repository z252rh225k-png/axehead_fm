import os
import json
from music_player.state.config import CATALOG_PATH, LOCAL_CATALOG_FALLBACK

def load_catalog():
    """Loads metadata matching records from catalog.json."""
    paths_to_try = [CATALOG_PATH, LOCAL_CATALOG_FALLBACK]
    for path in paths_to_try:
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[-] Failed to load catalog from {path}: {e}")
    return {}
