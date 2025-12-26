#!/usr/bin/env python3
import glob
import sys
import json
from pathlib import Path
try:
    from pygltflib import GLTF2
except Exception as e:
    print('Missing pygltflib:', e)
    sys.exit(2)

base = Path('tools/godot/ConvertedPrefabs/ImportedMeshes/Shadowbane/glb')
if not base.exists():
    print('No glb folder found at', base)
    sys.exit(1)

files = list(base.glob('*.glb'))
if not files:
    print('No .glb files found in', base)
    sys.exit(0)

results = []
failed = False
for p in files:
    file_result = { 'file': p.name, 'size': p.stat().st_size }
    try:
        g = GLTF2().load(str(p))
        meshes = len(g.meshes) if g.meshes else 0
        prims = sum(len(m.primitives) for m in (g.meshes or []))
        file_result.update({'meshes': meshes, 'primitives': prims, 'status': 'ok' if prims>0 else 'empty'})
        print(f"{p.name}: meshes={meshes}, primitives={prims}, size={p.stat().st_size} bytes")
        if prims == 0:
            failed = True
    except Exception as e:
        failed = True
        file_result.update({'meshes': None, 'primitives': None, 'status': 'invalid', 'error': str(e)})
        print(f"{p.name}: INVALID -", e)
    results.append(file_result)

# write JSON report
report_dir = base.parent.parent.parent / 'godot' / 'import_reports'
report_dir.mkdir(parents=True, exist_ok=True)
report_path = report_dir / 'validate_report.json'
summary = { 'files': results, 'any_failed': failed }
try:
    report_path.write_text(json.dumps(summary, indent=2))
    print(f"Wrote JSON report to {report_path}")
except Exception as e:
    print('Failed to write JSON report:', e)

if failed:
    print('\nOne or more .glb files are invalid or contain zero primitives.')
    sys.exit(1)
