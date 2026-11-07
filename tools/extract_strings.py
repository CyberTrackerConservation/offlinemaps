#!/usr/bin/env python3
"""
Extract the translatable strings of a map package into a strings.<locale>.json catalog.

Usage:
    python3 tools/extract_strings.py --locale mn PACKAGE
    python3 tools/extract_strings.py --locale mn --merge strings.mn.json PACKAGE
    python3 tools/extract_strings.py --locale mn --out /path/strings.mn.json PACKAGE

PACKAGE is a package zip or an unpacked package directory. The catalog maps every
translatable source string of the package's lookup content to its translation; a
new catalog has empty values for the translator to fill. With --merge, the
translations already present in an existing catalog are kept, new source strings
are added with empty values, and entries whose source string no longer occurs are
dropped. When a dropped entry closely resembles a new source string (a typo fix or
a small rewording), its translation is carried over to the new string and the pair
is listed in the report for the translator to confirm. The report on stderr lists
how many strings are translated, missing, carried over and dropped, so the
translator only needs to look at what is empty or flagged.

Translatable strings (README §2.10): row path elements; view name, title and
subtitle; every block label; body values; link and notice text; attribute item
labels and string values. Strings without letters, such as "900", are omitted.
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
import zipfile
from pathlib import Path

LETTER = re.compile(r"[^\W\d_]")
LOCALE = re.compile(r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*$")
GEOMETRY_SUFFIXES = (".shp", ".geojson")


class Package:
    """Read-only view of a package zip or directory."""

    def __init__(self, path: Path):
        self.path = path
        self.zip = zipfile.ZipFile(path) if path.is_file() else None
        if self.zip:
            self.names = [n for n in self.zip.namelist() if not n.endswith("/")]
        else:
            self.names = sorted(p.name for p in path.iterdir() if p.is_file())

    def read_json(self, name: str):
        data = self.zip.read(name) if self.zip else (self.path / name).read_bytes()
        return json.loads(data.decode("utf-8-sig"))

    def content_files(self) -> list[str]:
        """Content files of lookup layers, or of every layer that has lookup geometry."""
        names = set(self.names)
        if "layers.json" in names:
            layers = self.read_json("layers.json")
            basenames = [Path(layer["filename"]).stem for layer in layers if layer.get("lookup")]
        else:
            basenames = sorted({Path(n).stem for n in self.names if n.lower().endswith(GEOMETRY_SUFFIXES)})
        return [f"{b}.json" for b in basenames if f"{b}.json" in names and not is_catalog(f"{b}.json")]


def is_catalog(name: str) -> bool:
    parts = name.split(".")
    return len(parts) == 3 and parts[0] == "strings" and parts[2] == "json" and bool(LOCALE.match(parts[1]))


def translatable(value) -> bool:
    return isinstance(value, str) and bool(LETTER.search(value))


def row_strings(row: dict):
    yield from row.get("path", [])
    view = row.get("view", {})
    for key in ("name", "title", "subtitle"):
        yield view.get(key)
    for block in view.get("blocks", []):
        yield block.get("label")
        kind = block.get("type")
        if kind == "body":
            yield block.get("value")
        elif kind in ("link", "notice"):
            yield block.get("text")
        elif kind == "attributes":
            for item in block.get("items", []):
                yield item.get("label")
                yield item.get("value")


def package_strings(package: Package) -> tuple[list[str], dict[str, int]]:
    """Unique translatable strings in first-seen order, and the count per content file."""
    sources: list[str] = []
    seen: set[str] = set()
    per_file: dict[str, int] = {}
    for name in package.content_files():
        count = 0
        for dataset in package.read_json(name).get("datasets", []):
            for row in dataset.get("rows", []):
                for value in row_strings(row):
                    if translatable(value):
                        count += 1
                        if value not in seen:
                            seen.add(value)
                            sources.append(value)
        per_file[name] = count
    return sources, per_file


def carry_over(missing: list[str], dropped: dict[str, str], threshold: float) -> list[tuple[str, str, str, float]]:
    """Pair new source strings with dropped entries that closely resemble them, best matches first, one to one.

    Returns (new source, old source, translation, similarity).
    """
    scored = []
    for new in missing:
        matcher = difflib.SequenceMatcher(None, new)
        for old, translation in dropped.items():
            if not translation:
                continue
            matcher.set_seq2(old)
            if matcher.real_quick_ratio() < threshold or matcher.quick_ratio() < threshold:
                continue
            ratio = matcher.ratio()
            if ratio >= threshold:
                scored.append((ratio, new, old, translation))
    scored.sort(key=lambda item: -item[0])
    used_new: set[str] = set()
    used_old: set[str] = set()
    result = []
    for ratio, new, old, translation in scored:
        if new in used_new or old in used_old:
            continue
        used_new.add(new)
        used_old.add(old)
        result.append((new, old, translation, ratio))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("package", type=Path, help="package zip or unpacked package directory")
    parser.add_argument("--locale", required=True, help="BCP 47 tag of the target language, e.g. mn or fr-CA")
    parser.add_argument("--merge", type=Path, help="existing catalog whose translations are kept")
    parser.add_argument("--out", type=Path, help="output path (default: strings.<locale>.json in the current directory)")
    parser.add_argument("--fuzzy", type=float, default=0.85, metavar="RATIO",
                        help="similarity (0-1) above which a dropped entry's translation is carried over to a new source string; 0 disables (default 0.85)")
    args = parser.parse_args()

    if not LOCALE.match(args.locale):
        parser.error(f"not a BCP 47 language tag: {args.locale}")
    if not args.package.exists():
        parser.error(f"package not found: {args.package}")

    package = Package(args.package)
    sources, per_file = package_strings(package)
    if not per_file:
        print("No lookup content files found in the package.", file=sys.stderr)
        return 1

    existing: dict = {}
    if args.merge:
        existing = json.loads(args.merge.read_text(encoding="utf-8-sig"))
        if not isinstance(existing, dict):
            parser.error(f"not a catalog object: {args.merge}")

    catalog = {source: existing.get(source, "") for source in sources}
    dropped = {old: existing[old] for old in existing if old not in catalog}
    carried = []
    if args.fuzzy > 0 and dropped:
        missing = [source for source, value in catalog.items() if not value]
        carried = carry_over(missing, dropped, args.fuzzy)
        for new, old, translation, _ in carried:
            catalog[new] = translation
            del dropped[old]
    translated = sum(1 for value in catalog.values() if value)

    out = args.out or Path(f"strings.{args.locale}.json")
    out.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for name, count in per_file.items():
        print(f"{name}: {count} translatable strings", file=sys.stderr)
    print(f"{out}: {len(catalog)} unique strings, {translated} translated, {len(catalog) - translated} missing", file=sys.stderr)
    if carried:
        print(f"carried over {len(carried)} translations from edited source strings; confirm each:", file=sys.stderr)
        for new, old, translation, ratio in carried:
            print(f"  {ratio:.2f}  old: {old}\n        new: {new}\n        mn:  {translation}".replace("mn:", f"{args.locale}:"), file=sys.stderr)
    if dropped:
        print(f"dropped {len(dropped)} entries whose source string no longer occurs:", file=sys.stderr)
        for old in dropped:
            print(f"  {old}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
