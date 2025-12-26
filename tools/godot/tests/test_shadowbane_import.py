import argparse
import os
import subprocess
import sys
import time

parser = argparse.ArgumentParser()
parser.add_argument("--godot-binary", default=r"C:\Users\Gordo\OneDrive\Desktop\Godot_v4.5.1-stable_win64.exe")
parser.add_argument("--project", default=r"C:\Users\Gordo\Downloads\mcp-unity-main\mcp-unity-main\My project")
parser.add_argument("--timeout", type=int, default=20)


def main(argv=None):
    args = parser.parse_args(argv)

    godot = args.godot_binary
    proj = args.project
    scene_expected = os.path.join(proj, "ConvertedPrefabs", "Shadowbane_demo.tscn")
    print("Expecting scene:", scene_expected)
    cmd = [godot, "--headless", "--path", proj, "-s", "res://tools/godot/run_shadowbane_import.gd", "--"]
    print("Running:", " ".join(cmd))
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        stdout, stderr = proc.communicate(timeout=args.timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate()
    print('=== GODOT STDOUT ===')
    print(stdout)
    print('=== GODOT STDERR ===')
    print(stderr)
    print('RC', proc.returncode)
    if proc.returncode != 0:
        print('Godot failed, aborting')
        return 2

    success_file = os.path.join(proj, "ConvertedPrefabs", "Shadowbane_import.success")
    meta_file = os.path.join(proj, "ConvertedPrefabs", "Shadowbane_import.meta.json")
    if os.path.exists(success_file):
        print('Success marker found:', success_file)
        return 0
    elif os.path.exists(meta_file):
        print('Meta file found (fallback success):', meta_file)
        return 0
    elif os.path.exists(scene_expected):
        print('Scene was created:', scene_expected)
        return 0
    else:
        print('Failure: no success marker, meta file, or scene found')
        return 3


if __name__ == '__main__':
    sys.exit(main())