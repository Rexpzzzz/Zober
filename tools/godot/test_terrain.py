"""Simple smoke test for the headless terrain bridge.

Usage:
  python tools/godot/test_terrain.py --godot-binary <path> --project <path> --heightmap <path-inside-project>

Defaults are convenient for local dev; override as needed.
"""
import argparse
import os
import subprocess
import sys
import time

parser = argparse.ArgumentParser()
parser.add_argument("--godot-binary", default=r"C:\Users\Gordo\OneDrive\Desktop\Godot_v4.5.1-stable_win64.exe")
parser.add_argument("--project", default=r"C:\Users\Gordo\OneDrive\Documents\new-game-project")
parser.add_argument("--heightmap", default=r"ConvertedPrefabs/heightmap.png")
parser.add_argument("--timeout", type=int, default=20)


def main(argv=None):
    args = parser.parse_args(argv)

    godot = args.godot_binary
    proj = args.project
    heightmap = args.heightmap

    # Ensure ConvertedPrefabs exists and write a tiny 8x8 heightmap for fast, deterministic tests
    conv_dir = os.path.join(proj, "ConvertedPrefabs")
    os.makedirs(conv_dir, exist_ok=True)
    try:
        from PIL import Image
        img = Image.new("L", (8, 8), color=128)
        img.save(os.path.join(conv_dir, os.path.basename(heightmap)))
        print("Wrote tiny heightmap to", os.path.join(conv_dir, os.path.basename(heightmap)))
    except Exception as e:
        print("Could not auto-generate tiny heightmap (Pillow missing?):", e)

    scene_basename = os.path.splitext(os.path.basename(heightmap))[0]
    expected_scene = os.path.join(proj, "ConvertedPrefabs", scene_basename + "_terrain.tscn")
    print("Expecting scene:", expected_scene)

    cmd = [godot, "--headless", "--path", proj, "-s", "res://tools/godot/run_terrain_bridge.gd", "--"]
    print("Running:", " ".join(cmd))
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except FileNotFoundError:
        print("Godot binary not found at:", godot)
        return 2

    start = time.time()
    try:
        stdout, stderr = proc.communicate(timeout=args.timeout)
    except Exception as e:
        proc.kill()
        stdout, stderr = proc.communicate()
        print("Subprocess error:", e)

    print("=== GODOT STDOUT ===")
    print(stdout)
    print("=== GODOT STDERR ===")
    print(stderr)
    rc = proc.returncode
    print("Godot exit code:", rc)
    if rc != 0:
        print("Godot failed to run bridge; exit code", rc)
        return 3

    if os.path.exists(expected_scene):
        print("Success: terrain scene generated:", expected_scene)
        # Check for metadata JSON
        meta_path = os.path.join(os.path.dirname(expected_scene), scene_basename + "_terrain.meta.json")
        if os.path.exists(meta_path):
            print("Metadata found:", meta_path)
            return 0
        else:
            print("Warning: metadata not found (expected at):", meta_path)
            # still consider as success but warn
            return 0
    else:
        print("Failure: expected scene missing:", expected_scene)
        return 4


if __name__ == "__main__":
    sys.exit(main())
