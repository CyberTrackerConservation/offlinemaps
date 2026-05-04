#!/usr/bin/env python3
"""
Convert a directory of legacy Legal Atlas data into the new content-package format.

For every file in --input-dir:
  - layers.json is copied verbatim.
  - Other *.json files are converted to the new format and validated against the schema.
  - All non-JSON files (.shp, .geojson, .dbf, ...) are copied verbatim.

Usage:
    python convert_old_to_new.py [--input-dir old_format_data] [--output-dir new_format_data] \\
        [--schema package-schema.json] [--package-language en] [--default-locale en-US]
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any

try:
    import jsonschema
except ImportError as exc:
    print("Error: jsonschema is not installed. Install it with: pip install jsonschema", file=sys.stderr)
    raise SystemExit(2) from exc


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "dataset"


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def add_attribute(items: list[dict[str, Any]], label: str, fmt: str, value: Any) -> None:
    if value is None:
        return
    if isinstance(value, str) and value == "":
        return
    if isinstance(value, list) and len(value) == 0:
        return
    items.append({"label": label, "format": fmt, "value": value})


def convert_country(country_obj: dict[str, Any]) -> dict[str, Any]:
    country = country_obj["Country"]
    unique_geography = country_obj["Unique Geography"]
    unique_geography_id = str(country_obj["Unique Geography ID"])
    file_name = country_obj.get("File Name")

    rows: list[dict[str, Any]] = []

    for category1 in country_obj.get("Tag Categories", []):
        first_level = category1["1st Level Tag Category"]
        for category2 in category1.get("2nd Level Tag Categories", []):
            second_level = category2["2nd Level Tag Category"]
            for detail in category2.get("Tagging Details", []):
                summary = detail.get("Summary", "")
                tag_ref = detail.get("Tag Ref", "")
                law = detail.get("Law", "")
                toc = detail.get("Toc", "")
                primary_details = detail.get("Primary Tag Details", "")
                penalties = detail.get("Penalties Details") or []

                blocks: list[dict[str, Any]] = []

                if primary_details:
                    blocks.append({
                        "type": "body",
                        "label": "Details",
                        "format": "html",
                        "value": primary_details,
                    })

                if penalties:
                    penalty_obj = penalties[0]
                    penalty_items: list[dict[str, Any]] = []
                    for key in sorted(penalty_obj.keys()):
                        value = penalty_obj[key]
                        add_attribute(
                            penalty_items,
                            key,
                            "json" if isinstance(value, (dict, list)) else "text",
                            value,
                        )
                    if penalty_items:
                        blocks.append({"type": "attributes", "label": "Penalties", "items": penalty_items})

                if not blocks or not law:
                    continue

                row = {
                    "path": [country, unique_geography, first_level, second_level],
                    "view": {
                        "name": f"{summary} ({tag_ref})",
                        "title": law,
                        "blocks": blocks,
                    },
                }
                if toc:
                    row["view"]["subtitle"] = toc

                rows.append(row)

    dataset = {
        "id": f"legal-{slugify(country)}-ugid-{slugify(unique_geography_id)}",
        "filter": {"featureIds": ["*"]},
        "rows": rows,
    }
    if file_name:
        dataset["source"] = {"fileName": file_name}
    return dataset


def convert_package(old_data: Any, package_language: str, default_locale: str | None) -> dict[str, Any]:
    if isinstance(old_data, dict):
        country_objects = [old_data]
    elif isinstance(old_data, list):
        country_objects = old_data
    else:
        raise ValueError("Input JSON must be an object or an array of objects.")

    package: dict[str, Any] = {"content": {"id": "converted-content-package", "language": package_language}, "datasets": []}
    if default_locale:
        package["content"]["defaultLocale"] = default_locale

    for country_obj in country_objects:
        package["datasets"].append(convert_country(country_obj))

    return package


def format_error_path(error: jsonschema.ValidationError) -> str:
    path = "$"
    for part in error.absolute_path:
        path += f"[{part}]" if isinstance(part, int) else f".{part}"
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input-dir", type=Path, default=Path("old_format_data"))
    parser.add_argument("--output-dir", type=Path, default=Path("new_format_data"))
    parser.add_argument("--schema", type=Path, default=Path(__file__).resolve().parent.parent / "package-schema.json")
    parser.add_argument("--package-language", default="en")
    parser.add_argument("--default-locale", default="en-US")
    args = parser.parse_args()

    if not args.input_dir.is_dir():
        print(f"Error: input directory does not exist: {args.input_dir}", file=sys.stderr)
        return 2

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for existing in args.output_dir.iterdir():
        if existing.is_dir() and not existing.is_symlink():
            shutil.rmtree(existing)
        else:
            existing.unlink()

    schema = load_json(args.schema)
    validator_cls = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)
    validator = validator_cls(schema)

    converted = 0
    copied = 0
    invalid: list[str] = []

    for src in sorted(args.input_dir.iterdir()):
        if not src.is_file():
            continue
        dst = args.output_dir / src.name

        if src.name == "layers.json":
            layers = load_json(src)
            for layer in layers:
                layer.pop("legalAtlas", None)
                layer["lookup"] = True
            with dst.open("w", encoding="utf-8") as f:
                json.dump(layers, f, ensure_ascii=False, indent=2)
            with (args.output_dir / "package.json").open("w", encoding="utf-8") as f:
                json.dump({
                    "id": "LegalAtlas",
                    "name": "Legal Atlas Mongolia",
                    "version": "1",
                }, f, ensure_ascii=False, indent=2)
            copied += 2
            continue

        if src.suffix.lower() == ".geojson":
            geo = load_json(src)
            synthesized = 0
            next_id = 1
            for feature in geo.get("features", []):
                if "id" in feature:
                    continue
                props = feature.get("properties") or {}
                if "fid" in props:
                    feature["id"] = props.pop("fid")
                else:
                    feature["id"] = next_id
                    next_id += 1
                    synthesized += 1
            if synthesized:
                print(f"  warning: {src.name}: synthesized sequential ids for {synthesized} feature(s) with no id/fid")
            with dst.open("w", encoding="utf-8") as f:
                json.dump(geo, f, ensure_ascii=False, indent=2)
            copied += 1
            continue

        if src.suffix.lower() != ".json":
            shutil.copy2(src, dst)
            copied += 1
            continue

        old_data = load_json(src)
        new_data = convert_package(old_data, args.package_language, args.default_locale)
        with dst.open("w", encoding="utf-8") as f:
            json.dump(new_data, f, ensure_ascii=False, indent=2)
        converted += 1

        errors = sorted(validator.iter_errors(new_data), key=lambda e: list(e.absolute_path))
        if errors:
            invalid.append(src.name)
            print(f"INVALID: {dst}")
            for i, error in enumerate(errors, start=1):
                print(f"  {i}. {format_error_path(error)}: {error.message}")

    print(f"Converted {converted} JSON file(s), copied {copied} other file(s) to {args.output_dir}.")
    if invalid:
        print(f"{len(invalid)} file(s) failed schema validation: {', '.join(invalid)}", file=sys.stderr)
        return 1
    print("All converted files validate against the schema.")

    archive_path = args.output_dir.parent / "LegalAtlasLayers_ENG.zip"
    archived = 0
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for entry in sorted(args.output_dir.iterdir()):
            if not entry.is_file():
                continue
            zf.write(entry, arcname=entry.name)
            archived += 1
    print(f"Wrote {archive_path} ({archived} file(s) at archive root).")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
