#!/usr/bin/env python3
"""
Build a zip for each demo folder under demos/.

Each subdirectory of demos/ is packaged into a sibling <name>.zip with files at
the archive root (no enclosing directory). Pre-existing zips are overwritten.
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path


def build(demo_dir: Path, archive_path: Path) -> int:
    archive_path.unlink(missing_ok=True)
    file_count = 0
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for entry in sorted(demo_dir.iterdir()):
            if not entry.is_file():
                continue
            zf.write(entry, arcname=entry.name)
            file_count += 1
    return file_count


def main() -> int:
    demos_root = Path(__file__).resolve().parent
    built = 0
    for demo in sorted(demos_root.iterdir()):
        if not demo.is_dir():
            continue
        archive_path = demos_root / f"{demo.name}.zip"
        n = build(demo, archive_path)
        print(f"{archive_path.name}: {n} file(s) from {demo.name}/")
        built += 1
    if built == 0:
        print("No demo folders found.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
