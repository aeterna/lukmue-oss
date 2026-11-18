#!/usr/bin/env python3
"""Check project manifests (project.toml) under selected directories of a root.

Standard library only (Python 3.11+). The schema is loaded from
project.schema.json located next to this file, so the whole tools/project-check
directory can be copied into another repository unchanged.

Usage:
    check_projects.py --root DIR --visibility private|public --dir NAME [--dir NAME ...]
"""

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path

MANIFEST_NAME = "project.toml"
SCHEMA_PATH = Path(__file__).resolve().parent / "project.schema.json"
_JSON_TYPES = {"string": str, "object": dict}


def load_schema(path=SCHEMA_PATH):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def validate(data, schema):
    """Validate a parsed TOML table against the supported schema subset.

    Supported keywords: type (string, object), required, additionalProperties
    (false only), enum, pattern, minLength. Returns a list of message strings.
    """
    if not isinstance(data, dict):
        return ["expected a table"]

    errors = []
    for key in schema.get("required", []):
        if key not in data:
            errors.append(f"missing required field '{key}'")

    properties = schema.get("properties", {})
    if schema.get("additionalProperties") is False:
        for key in sorted(data):
            if key not in properties:
                errors.append(f"unknown field '{key}'")

    for key, sub in properties.items():
        if key in data:
            errors.extend(_check_value(key, data[key], sub))
    return errors


def _check_value(key, value, sub):
    expected = _JSON_TYPES.get(sub.get("type"))
    if expected is not None and not isinstance(value, expected):
        return [f"field '{key}' must be a {sub['type']}, got {type(value).__name__}"]

    errors = []
    if "enum" in sub and value not in sub["enum"]:
        allowed = ", ".join(str(item) for item in sub["enum"])
        errors.append(f"field '{key}' must be one of {allowed}; got {value!r}")
    if "pattern" in sub and isinstance(value, str):
        if not re.search(sub["pattern"], value):
            errors.append(
                f"field '{key}' value {value!r} does not match pattern {sub['pattern']}"
            )
    if "minLength" in sub and isinstance(value, str) and len(value) < sub["minLength"]:
        errors.append(f"field '{key}' must have length >= {sub['minLength']}")
    return errors


def check_manifest(manifest, folder_name, visibility, schema):
    """Return the problem messages for one project.toml (without path prefix)."""
    try:
        with manifest.open("rb") as handle:
            data = tomllib.load(handle)
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        return [f"invalid TOML: {exc}"]
    except OSError as exc:
        return [f"cannot read file: {exc.strerror or exc}"]

    problems = validate(data, schema)
    if not isinstance(data, dict):
        return problems

    name = data.get("name")
    if isinstance(name, str) and name != folder_name:
        problems.append(f"name {name!r} does not match folder name {folder_name!r}")

    manifest_visibility = data.get("visibility")
    if isinstance(manifest_visibility, str) and manifest_visibility != visibility:
        problems.append(
            f"visibility {manifest_visibility!r} does not match --visibility {visibility!r}"
        )

    if visibility == "public" and data.get("type") == "helper":
        problems.append("type 'helper' is not allowed for public projects")
    return problems


def run_checks(root, dir_names, visibility, schema):
    """Check every project under the given directories.

    Returns (problems, project_count). Each problem is a full
    '<relative path>: <message>' string.
    """
    problems = []
    count = 0
    for dir_name in dir_names:
        base = root / dir_name
        if not base.exists():
            continue
        if not base.is_dir():
            problems.append(f"{base.relative_to(root).as_posix()}: not a directory")
            continue

        for project in sorted(base.iterdir()):
            if project.name.startswith(".") or not project.is_dir():
                continue
            count += 1
            manifest = project / MANIFEST_NAME
            rel = manifest.relative_to(root).as_posix()
            if not manifest.is_file():
                problems.append(f"{rel}: missing {MANIFEST_NAME}")
                continue
            for message in check_manifest(manifest, project.name, visibility, schema):
                problems.append(f"{rel}: {message}")
    return problems, count


def build_parser():
    parser = argparse.ArgumentParser(
        description="Validate project.toml manifests in the given directories."
    )
    parser.add_argument("--root", required=True, help="repository root containing the directories")
    parser.add_argument(
        "--visibility", required=True, choices=["private", "public"],
        help="expected visibility of every project",
    )
    parser.add_argument(
        "--dir", dest="dirs", action="append", required=True, metavar="NAME",
        help="directory under root whose subdirectories are projects (repeatable)",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    root = Path(args.root)
    if not root.is_dir():
        print(f"{args.root}: root is not a directory", file=sys.stderr)
        return 1

    problems, count = run_checks(root, args.dirs, args.visibility, load_schema())
    if problems:
        for problem in problems:
            print(problem, file=sys.stderr)
        return 1
    print(f"ok: {count} project(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
