import json
from pathlib import Path

GODOT_PROJECT = Path(r"C:/Users/Gordo/OneDrive/Documents/new-game-project")
TARGET_DIR = GODOT_PROJECT / "ConvertedPrefabs"
REGISTRY = TARGET_DIR / 'biome_registry.json'
GALLERY_TSCN = TARGET_DIR / 'BiomeGallery.tscn'

if not REGISTRY.exists():
    print('Registry not found:', REGISTRY)
    raise SystemExit(1)

registry = json.loads(REGISTRY.read_text(encoding='utf-8'))
keys = sorted(registry.keys())

# Build ext_resource entries and instance nodes, spacing each by 2 units along X
exts = []
nodes = []
for i, name in enumerate(keys, start=1):
    path = registry[name].replace('res://', '')
    fname = Path(path).name
    exts.append((i, fname))
    pos_x = (i - 1) * 2.5
    # Instance node
    nodes.append((i, name, pos_x))

# Compose tscn
lines = []
lines.append('[gd_scene load_steps=2 format=3]')
for idn, fname in exts:
    lines.append(f'[ext_resource path="res://ConvertedPrefabs/{fname}" type="PackedScene" id={idn}]')
lines.append('')
lines.append('[node name="BiomeGallery" type="Node3D"]')
for idn, name, pos_x in nodes:
    lines.append(f'[node name="inst_{name}" instance=ExtResource( {idn} ) parent="BiomeGallery"]')
    # Add transform if possible (simple translation)
    lines.append(f'position = Vector3({pos_x}, 0.0, 0.0)')

GALLERY_TSCN.write_text('\n'.join(lines), encoding='utf-8')
print('Wrote', GALLERY_TSCN)