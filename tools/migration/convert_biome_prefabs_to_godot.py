"""Convert Unity biome prefabs to Godot scenes with optional full-mesh conversion.

This updated script will:
 - Detect if a prefab's MeshFilter references an external mesh (non-zero GUID).
 - If a model asset (.fbx/.obj/.gltf/.glb) with that GUID exists in Assets/, copy it to
   `ConvertedPrefabs/ImportedMeshes` so Godot can import it.
 - Otherwise fallback to a BoxMesh placeholder as before.

For simple cube prefabs (internal mesh GUID = all-zero) this remains fast and safe.
"""

import argparse
import logging
import re
import os
import sys
import shutil
from pathlib import Path

# Configuration
UNITY_PROJECT = Path(r"C:/Users/Gordo/Downloads/mcp-unity-main/mcp-unity-main/My project")
PREFAB_DIR = UNITY_PROJECT / "Assets" / "WorldAssets" / "Prefabs"
# Write to local temp location first to avoid OneDrive sync truncation issues
TEMP_OUTPUT = Path(r"C:/Users/Gordo/AppData/Local/Temp/GodotConversion")
TARGET_DIR = TEMP_OUTPUT / "ConvertedPrefabs"
IMPORTED_MESH_DIR = TARGET_DIR / "ImportedMeshes"
# Final destination (will be copied after conversion)
GODOT_PROJECT = Path(r"C:/Users/Gordo/OneDrive/Documents/new-game-project")
FINAL_TARGET = GODOT_PROJECT / "ConvertedPrefabs"

os.makedirs(TARGET_DIR, exist_ok=True)
os.makedirs(IMPORTED_MESH_DIR, exist_ok=True)

# CLI flags (do NOT parse at import time; tests import helpers)
parser = argparse.ArgumentParser(description="Convert Unity biome prefabs to Godot scenes.")
parser.add_argument("--unity-project", type=str, default=str(UNITY_PROJECT), help="Path to Unity project")
parser.add_argument("--final-target", type=str, default=str(FINAL_TARGET), help="Final Godot target directory")
parser.add_argument("--dry-run", action="store_true", help="Do not perform file copy; show actions only")
parser.add_argument("--overwrite", action="store_true", help="Overwrite existing files in final target without prompt")
parser.add_argument("--list-backups", action="store_true", help="List existing ImportedMeshes backups under the final target and exit")
parser.add_argument("--verbose", action="store_true", help="Enable verbose debug logging")

# NOTE: Do not call parser.parse_args() at import time. Tests import utility functions from this
# module (e.g., `list_backups`) and should not trigger CLI parsing. Call `main()` instead.

def list_backups(final_target: Path):
    """Return a sorted list of backup directories for ImportedMeshes under the final target."""
    backups = []
    im_dir = final_target / 'ImportedMeshes'
    parent = im_dir.parent
    if parent.exists():
        for d in parent.iterdir():
            if d.is_dir() and d.name.startswith('ImportedMeshes_backup_'):
                backups.append(d)
    backups.sort()
    return backups

# Guard CLI-specific behavior so importing this module for tests does not execute code.
if __name__ == '__main__':
    args = parser.parse_args()
    if args.list_backups:
        found = list_backups(Path(args.final_target))
        if not found:
            logging.info("No ImportedMeshes backups found under %s", args.final_target)
        else:
            logging.info("Found %d ImportedMeshes backup(s):", len(found))
            for b in found:
                logging.info("  %s", b)
        sys.exit(0)
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")
    _run_conversion(Path(args.unity_project), Path(args.final_target), args.dry_run, args.overwrite)

# Helper: write file atomically and verify contents
import tempfile

def atomic_write(path: Path, content: str, encoding: str = 'utf-8') -> None:
    """Write content to a temporary file and atomically replace target file.
    This reduces the risk of leaving a truncated file if the process is interrupted
    or if a cloud sync (OneDrive) interferes during write.
    Also verifies that the file appears to be non-empty after write.
    """
    tmp_fd, tmp_path = tempfile.mkstemp(prefix=path.name + '.', dir=str(path.parent))
    try:
        with os.fdopen(tmp_fd, 'w', encoding=encoding) as f:
            f.write(content)
        # Replace atomically
        os.replace(tmp_path, path)
        # Basic verification
        written = path.stat().st_size
        if written == 0:
            raise IOError(f"Wrote zero bytes to {path}")
        logging.debug(f"Wrote {written} bytes to {path}")
    except Exception as e:
        # Clean up temp file on error
        try:
            os.remove(tmp_path)
        except Exception:
            pass
        logging.exception(f"Failed to write {path}: {e}")
        raise

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

def _run_conversion(unity_project: Path, final_target: Path, dry_run: bool, overwrite: bool):
    """Run the conversion process. This is separated from CLI parsing so tests can import
    the module without triggering command-line parsing or execution.
    """
    prefab_dir = unity_project / "Assets" / "WorldAssets" / "Prefabs"

    prefabs = []
    if prefab_dir.exists():
        for p in prefab_dir.glob("BiomePrefab_*.prefab"):
            prefabs.append(p)
    else:
        logging.warning(f"Prefab folder not found: {prefab_dir}")

    if not prefabs:
        logging.info("No BiomePrefab_*.prefab files found. Exiting.")
        return

    logging.info(f"Found {len(prefabs)} prefab(s) to convert")

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
                    logging.info(f"Prefab {name} references external asset: {asset} (ext {ext})")
                    # Copy the asset into the Godot project for import using GUID-prefixed name to avoid collisions
                    dest = IMPORTED_MESH_DIR / f"{guid}_{asset.name}"
                    try:
                        if dry_run:
                            logging.info(f"[DRY-RUN] Would copy {asset} -> {dest}")
                        else:
                            shutil.copy2(asset, dest)
                            logging.info(f"Copied {asset} -> {dest}")
                        # For .fbx/.glb/.gltf, Godot imports them as PackedScene
                        if ext in ['.fbx', '.glb', '.gltf']:
                            ext_resource_entry = f"[ext_resource path=\"res://ConvertedPrefabs/ImportedMeshes/{dest.name}\" type=\"PackedScene\" id=1]\n"
                            # We'll instance the PackedScene
                            scene_nodes = f"[node name=\"inst_{name}\" instance=ExtResource( 1 ) type=\"Node\" parent=\"\"]\n"
                        elif ext in ['.obj']:
                            # OBJ often imports as a Mesh resource; we reference it as a Mesh
                            ext_resource_entry = f"[ext_resource path=\"res://ConvertedPrefabs/ImportedMeshes/{dest.name}\" type=\"ArrayMesh\" id=1]\n"
                            scene_nodes = f"[node name=\"{name}\" type=\"MeshInstance3D\"]\nmesh = ExtResource( 1 )\n"
                        else:
                            # Unknown asset type: fallback to PackedScene reference
                            ext_resource_entry = f"[ext_resource path=\"res://ConvertedPrefabs/ImportedMeshes/{dest.name}\" type=\"PackedScene\" id=1]\n"
                            scene_nodes = f"[node name=\"inst_{name}\" instance=ExtResource( 1 ) type=\"Node\" parent=\"\"]\n"
                        chosen_mesh_resource = dest
                    except Exception as e:
                        logging.warning(f"Failed to copy asset {asset}: {e}. Falling back to BoxMesh.")
                else:
                    logging.info(f"Prefab {name} references GUID {guid} but no asset with that GUID found. Using BoxMesh.")
            else:
                logging.info(f"Prefab {name} uses internal primitive mesh (zero GUID); using BoxMesh.")
        else:
            logging.info(f"No mesh GUID found in {name}; using BoxMesh.")

        # Write StandardMaterial3D resource
        mat_path = TARGET_DIR / f"{name}.mat.tres"
        mat_contents = f"""[gd_resource type="StandardMaterial3D" load_steps=2 format=3]

[resource]
albedo_color = Color({r},{g},{b},{a})
"""
        # Write material atomically and verify
        try:
            atomic_write(mat_path, mat_contents)
        except Exception as e:
            logging.error(f"ERROR writing material for {name}: {e}")
            continue

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

[resource]
size = Vector3(1.0, 1.0, 1.0)
"""
            try:
                atomic_write(box_path, box_contents)
            except Exception as e:
                logging.error(f"ERROR writing boxmesh for {name}: {e}")
                continue

            scene_contents = f"""[gd_scene load_steps=2 format=3]
[ext_resource path="res://ConvertedPrefabs/{name}.boxmesh.tres" type="BoxMesh" id=1]
[ext_resource path="res://ConvertedPrefabs/{name}.mat.tres" type="StandardMaterial3D" id=2]

[node name="{name}" type="MeshInstance3D"]
mesh = ExtResource( 1 )
material/0 = ExtResource( 2 )

"""

            try:
                atomic_write(scene_path, scene_contents)
            except Exception as e:
                logging.error(f"ERROR writing scene for {name}: {e}")
                continue

            logging.info(f"Converted {pf} -> {scene_path}")

    logging.info(f"Conversion complete. Created resources in {TARGET_DIR}")


def _copy_to_final(final_target: Path, dry_run: bool, overwrite: bool):
    """Copy items from `TARGET_DIR` into `final_target` with backups and optional dry-run."""
    logging.info(f"\nCopying to OneDrive destination: {final_target}")
    os.makedirs(final_target, exist_ok=True)
    for item in TARGET_DIR.iterdir():
        if item.is_file():
            dest = final_target / item.name
            if dry_run:
                logging.info(f"[DRY-RUN] Would copy file {item.name} ({item.stat().st_size} bytes) to {dest}")
            else:
                if dest.exists() and not overwrite:
                    resp = input(f"Destination file {dest} exists. Overwrite? [y/N]: ")
                    if resp.strip().lower() != 'y':
                        logging.info(f"Skipping {dest}")
                        continue
                shutil.copy2(item, dest)
                logging.info(f"  Copied {item.name} ({item.stat().st_size} bytes)")
        elif item.is_dir() and item.name != "__pycache__":
            dest_dir = final_target / item.name
            if dry_run:
                logging.info(f"[DRY-RUN] Would copy directory {item.name}/ to {dest_dir}")
            else:
                # If the destination directory already exists, move it to a timestamped backup
                if dest_dir.exists():
                    t = __import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')
                    backup_dir = dest_dir.with_name(dest_dir.name + f"_backup_{t}")
                    try:
                        logging.info(f"Moving existing directory {dest_dir} -> {backup_dir}")
                        shutil.move(str(dest_dir), str(backup_dir))
                    except Exception as e:
                        logging.exception(f"Failed to move existing directory {dest_dir} to backup {backup_dir}: {e}")
                        if overwrite:
                            logging.info(f"Attempting to remove {dest_dir} due to --overwrite")
                            try:
                                shutil.rmtree(dest_dir)
                            except Exception as e2:
                                logging.exception(f"Failed to remove {dest_dir}: {e2}")
                                logging.error(f"Could not backup or remove {dest_dir}; skipping copy")
                                continue
                        else:
                            logging.error(f"Could not backup {dest_dir} and --overwrite not set; skipping copy")
                            continue
                try:
                    shutil.copytree(item, dest_dir)
                    logging.info(f"  Copied directory {item.name}/")
                except Exception as e:
                    logging.exception(f"Failed to copy directory {item} to {dest_dir}: {e}")
                    continue

    logging.info(f"All files copied to {final_target}")


def main(argv=None):
    args = parser.parse_args(argv)
    # CLI flags
    dry_run = args.dry_run
    overwrite = args.overwrite
    list_backups_flag = args.list_backups
    final_target = Path(args.final_target)
    unity_project = Path(args.unity_project)

    if list_backups_flag:
        found = list_backups(final_target)
        if not found:
            logging.info("No ImportedMeshes backups found under %s", final_target)
        else:
            logging.info("Found %d ImportedMeshes backup(s):", len(found))
            for b in found:
                logging.info("  %s", b)
        return

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")

    # Ensure target directories exist
    os.makedirs(TARGET_DIR, exist_ok=True)
    os.makedirs(IMPORTED_MESH_DIR, exist_ok=True)

    _run_conversion(unity_project, final_target, dry_run, overwrite)
    _copy_to_final(final_target, dry_run, overwrite)


if __name__ == "__main__":
    main()
