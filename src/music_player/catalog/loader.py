import os
import json
from music_player.state.config import (
    BUILTIN_CATALOG_PATH, LOCAL_BUILTIN_CATALOG_FALLBACK,
    USER_CATALOG_PATH, LOCAL_USER_CATALOG_FALLBACK
)

def _load_catalog_file(paths):
    """Load catalog from first available path."""
    for path in paths:
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[-] Failed to load catalog from {path}: {e}")
    return {}

def load_catalog():
    """
    Loads and merges built-in and user catalogs.
    Returns a dict with entries from both catalogs.
    Built-in entries can be overridden by user entries with the same ID.
    """
    # Load built-in catalog
    builtin = _load_catalog_file([BUILTIN_CATALOG_PATH, LOCAL_BUILTIN_CATALOG_FALLBACK])
    
    # Load user catalog
    user = _load_catalog_file([USER_CATALOG_PATH, LOCAL_USER_CATALOG_FALLBACK])
    
    # Merge: user entries can override built-in entries with same ID
    merged = builtin.copy()
    merged.update(user)
    
    return merged

def load_catalog_split():
    """
    Loads and returns catalogs separately with metadata.
    Returns {'builtin': {...}, 'user': {...}}
    """
    builtin = _load_catalog_file([BUILTIN_CATALOG_PATH, LOCAL_BUILTIN_CATALOG_FALLBACK])
    user = _load_catalog_file([USER_CATALOG_PATH, LOCAL_USER_CATALOG_FALLBACK])
    
    return {
        'builtin': builtin,
        'user': user
    }

def get_catalog_source(entry_id):
    """
    Determines if an entry is from built-in or user catalog.
    Returns 'builtin', 'user', or None if not found.
    """
    catalogs = load_catalog_split()
    if entry_id in catalogs['user']:
        return 'user'
    elif entry_id in catalogs['builtin']:
        return 'builtin'
    return None

def is_builtin_entry(entry_id):
    """Check if entry is from built-in catalog (read-only)."""
    return get_catalog_source(entry_id) == 'builtin'

def is_user_entry(entry_id):
    """Check if entry is from user catalog (editable)."""
    return get_catalog_source(entry_id) == 'user'

