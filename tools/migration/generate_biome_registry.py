from pathlib import Path
import json

GODOT_PROJECT = Path(r"C:/Users/Gordo/OneDrive/Documents/new-game-project")
TARGET_DIR = GODOT_PROJECT / "ConvertedPrefabs"

files = sorted(TARGET_DIR.glob('BiomePrefab_*.tscn'))
registry = {f.stem: f"res://ConvertedPrefabs/{f.name}" for f in files}
(TARGET_DIR / 'biome_registry.json').write_text(json.dumps(registry, indent=2), encoding='utf-8')
print('Wrote', TARGET_DIR / 'biome_registry.json')
