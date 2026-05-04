#!/usr/bin/env python3
"""
Validate a content package JSON file against the provided JSON Schema.

Usage:
    python validate_content_package.py schema.json content.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError as exc:
    print("Error: jsonschema is not installed. Install it with: pip install jsonschema", file=sys.stderr)
    raise SystemExit(2) from exc


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python validate_content_package.py schema.json content.json", file=sys.stderr)
        return 2

    schema_path = Path(sys.argv[1])
    content_path = Path(sys.argv[2])

    schema = load_json(schema_path)
    content = load_json(content_path)

    validator_cls = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)
    validator = validator_cls(schema)

    errors = sorted(validator.iter_errors(content), key=lambda e: list(e.absolute_path))

    if not errors:
        print(f"VALID: {content_path}")
        return 0

    print(f"INVALID: {content_path}")
    for i, error in enumerate(errors, start=1):
        path = "$"
        for part in error.absolute_path:
            if isinstance(part, int):
                path += f"[{part}]"
            else:
                path += f".{part}"
        print(f"{i}. {path}: {error.message}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
