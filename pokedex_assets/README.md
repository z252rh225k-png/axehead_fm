# Pokédex Assets Cache

This directory stores cached Pokémon data and sprites from the PokéAPI.

## Structure

The cache is populated automatically when the music player starts:
- **Gen 1 Pokémon (1-151)**: Pre-cached with 1-bit monochrome sprites
- **Higher Gens (152+)**: Fetched on-demand and cached for future use

Each Pokémon is stored as:
- `{id}.json` - Metadata (name, types, height, weight)
- `{id}.png` - 1-bit sprite image

## Example

When a Pokédex tag with ID 025 is scanned:
- The player loads `/pokedex_assets/25.json` and `/pokedex_assets/25.png`
- Displays Pikachu on the OLED display

## First Run

On first startup, the player will automatically download and cache all original 151 Pokémon from PokéAPI. This takes approximately 2-5 minutes depending on network speed.

## NFC Tag Format

Pokédex tags use the format: `poke_XXX` where XXX is:
- A Pokémon ID number (e.g., `poke_025` for Pikachu)
- `poke_ball` or `poke_random` for a random Gen 1 Pokémon

## Requirements

- `requests` - HTTP library for PokéAPI calls
- `Pillow` - Image processing for sprites
- Network access to https://pokeapi.co/ for live fetching and initial cache setup
