"""Convert Unity biome prefabs to Godot scenes with optional full-mesh conversion.

This updated script will:
 - Detect if a prefab's MeshFilter references an external mesh (non-zero GUID).
 - If a model asset (.fbx/.obj/.gltf/.glb) with that GUID exists in Assets/, copy it to
   `ConvertedPrefabs/ImportedMeshes` so Godot can import it.
 - Otherwise fallback to a BoxMesh placeholder as before.

For simple cube prefabs (internal mesh GUID = all-zero) this remains fast and safe.
"""

import re
import os
import sys
import shutil
from pathlib import Path

# Configuration
UNITY_PROJECT = Path(r"C:/Users/Gordo/Downloads/mcp-unity-main/mcp-unity-main/My project")
PREFAB_DIR = UNITY_PROJECT / "Assets" / "WorldAssets" / "Prefabs"
GODOT_PROJECT = Path(r"C:/Users/Gordo/OneDrive/Documents/new-game-project")
TARGET_DIR = GODOT_PROJECT / "ConvertedPrefabs"
IMPORTED_MESH_DIR = TARGET_DIR / "ImportedMeshes"

os.makedirs(TARGET_DIR, exist_ok=True)
os.makedirs(IMPORTED_MESH_DIR, exist_ok=True)

# Regex to find color vector in prefab text: search for "m_Color:", fallback to generic 'color:'
COLOR_RE = re.compile(r"m_Color:\s*\{?\s*r:\s*([0-9\.\-eE]+)\s*,\s*g:\s*([0-9\.\-eE]+)\s*,\s*b:\s*([0-9\.\-eE]+)\s*,\s*a:\s*([0-9\.\-eE]+)\s*\}?")
GENERIC_COLOR_RE = re.compile(r"color:\s*\{?\s*([0-9\.\-eE]+)\s*,\s*([0-9\.\-eE]+)\s*,\s*([0-9\.\-eE]+)\s*,\s*([0-9\.\-eE]+)\s*\}?")
# Regex to extract mesh guid from MeshFilter: m_Mesh: {fileID: 10202, guid: <guid>, type: 0}
MESH_GUID_RE = re.compile(r"m_Mesh:\s*\{\s*fileID:\s*[0-9]+\s*,\s*guid:\s*([0-9a-fA-F]+)\s*,\s*type:\s*[0-9]+\s*\}")
ZERO_GUID = "00000000000000000000000000000000"

# Helper: search for a .meta file under the Unity assets whose 'guid: <guid>' matches
def find_asset_by_guid(guid: str):
    # Search Assets/ recursively for .meta files containing 'guid: <guid>'
    for meta in (UNITY_PROJECT / "Assets").rglob("*.meta"):
        try:
            text = meta.read_text()
        except Exception:
            continue
        if f"guid: {guid}" in text:
            # asset path is meta file path without .meta
            asset_path = meta.with_suffix("")
            if asset_path.exists():
                return asset_path
    return None

prefabs = []
if PREFAB_DIR.exists():
    for p in PREFAB_DIR.glob("BiomePrefab_*.prefab"):
        prefabs.append(p)
else:
    print("Prefab folder not found:", PREFAB_DIR)

if not prefabs:
    print("No BiomePrefab_*.prefab files found. Exiting.")
    sys.exit(0)

print(f"Found {len(prefabs)} prefab(s) to convert")

for pf in prefabs:
    name = pf.stem
    text = pf.read_text(errors='ignore')

    # color
    color_match = COLOR_RE.search(text)
    if not color_match:
        color_match = GENERIC_COLOR_RE.search(text)
    if color_match:
        r, g, b, a = [float(x) for x in color_match.groups()]
    else:
        r, g, b, a = (0.8, 0.8, 0.8, 1.0)

    # detect mesh GUID (if any)
    mesh_guid_match = MESH_GUID_RE.search(text)

    chosen_mesh_resource = None
    ext_resource_entry = ''
    scene_nodes = ''

    if mesh_guid_match:
        guid = mesh_guid_match.group(1)
        if guid != ZERO_GUID:
            asset = find_asset_by_guid(guid)
            if asset:
                ext = asset.suffix.lower()
                print(f"Prefab {name} references external asset: {asset} (ext {ext})")
                # Copy the asset into the Godot project for import
                dest = IMPORTED_MESH_DIR / asset.name
                try:
                    shutil.copy2(asset, dest)
                    print(f"Copied {asset} -> {dest}")
                    # For .fbx/.glb/.gltf, Godot imports them as PackedScene
                    if ext in ['.fbx', '.glb', '.gltf']:
                        ext_resource_entry = f"[ext_resource path=\"res://ConvertedPrefabs/ImportedMeshes/{asset.name}\" type=\"PackedScene\" id=1]\n"
                        # We'll instance the PackedScene
                        scene_nodes = f"[node name=\"inst_{name}\" instance=ExtResource( 1 ) type=\"Node\" parent=\"\"]\n"
                    elif ext in ['.obj']:
                        # OBJ often imports as a Mesh resource; we reference it as a Mesh
                        ext_resource_entry = f"[ext_resource path=\"res://ConvertedPrefabs/ImportedMeshes/{asset.name}\" type=\"ArrayMesh\" id=1]\n"
                        scene_nodes = f"[node name=\"{name}\" type=\"MeshInstance3D\"]\nmesh = ExtResource( 1 )\n"
                    else:
                        # Unknown asset type: fallback to PackedScene reference
                        ext_resource_entry = f"[ext_resource path=\"res://ConvertedPrefabs/ImportedMeshes/{asset.name}\" type=\"PackedScene\" id=1]\n"
                        scene_nodes = f"[node name=\"inst_{name}\" instance=ExtResource( 1 ) type=\"Node\" parent=\"\"]\n"
                    chosen_mesh_resource = dest
                except Exception as e:
                    print(f"Failed to copy asset {asset}: {e}. Falling back to BoxMesh.")
            else:
                print(f"Prefab {name} references GUID {guid} but no asset with that GUID found. Using BoxMesh.")
        else:
            print(f"Prefab {name} uses internal primitive mesh (zero GUID); using BoxMesh.")
    else:
        print(f"No mesh GUID found in {name}; using BoxMesh.")

    # Write StandardMaterial3D resource
    mat_path = TARGET_DIR / f"{name}.mat.tres"
    mat_contents = f"""[gd_resource type="StandardMaterial3D" load_steps=2 format=3]
albedo_color = Color({r},{g},{b},{a})
"""
    mat_path.write_text(mat_contents, encoding='utf-8')

    # Now compose the scene. If ext_resource_entry/scene_nodes are set, use them. Otherwise create BoxMesh + material
    scene_path = TARGET_DIR / f"{name}.tscn"
    if chosen_mesh_resource and scene_nodes:
        scene_contents = f"""[gd_scene load_steps=2 format=3]
{ext_resource_entry}[ext_resource path="res://ConvertedPrefabs/{name}.mat.tres" type="StandardMaterial3D" id=2]

{scene_nodes}

"""
        # If the scene is a MeshInstance3D node, assign material
        if 'MeshInstance3D' in scene_nodes:
            scene_contents = scene_contents.replace('\n\n', f"material/0 = ExtResource( 2 )\n\n")
    else:
        # Fallback: BoxMesh + material
        box_path = TARGET_DIR / f"{name}.boxmesh.tres"
        box_contents = f"""[gd_resource type="BoxMesh" load_steps=2 format=3]
size = Vector3(1.0, 1.0, 1.0)
"""
        box_path.write_text(box_contents, encoding='utf-8')

        scene_contents = f"""[gd_scene load_steps=2 format=3]
[ext_resource path="res://ConvertedPrefabs/{name}.boxmesh.tres" type="BoxMesh" id=1]
[ext_resource path="res://ConvertedPrefabs/{name}.mat.tres" type="StandardMaterial3D" id=2]

[node name="{name}" type="MeshInstance3D"]
mesh = ExtResource( 1 )
material/0 = ExtResource( 2 )

"""

    scene_path.write_text(scene_contents, encoding='utf-8')

    print(f"Converted {pf} -> {scene_path}")

print("Conversion complete. Created resources in", TARGET_DIR)
