#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate every pet package in the repository. Exits 1 if any check fails."""
import json
import re
import sys
from pathlib import Path

from PIL import Image

ATLAS_HEIGHT_BY_SPRITE_VERSION = {1: 1872, 2: 2288}
ATLAS_WIDTH = 1536
EXCLUDED_DIRS = {".git", "worktrees", "__pycache__", "scripts", "tests"}
LOCAL_PATH = re.compile("/" + "Users/|/private/" + "tmp|Drop" + "box/")
FRAME_REFERENCE = re.compile(r'"(frames/[^"]+)"')


def repo_files(root):
    for path in sorted(root.rglob("*")):
        relative_parts = path.relative_to(root).parts
        if path.is_file() and not EXCLUDED_DIRS.intersection(relative_parts):
            yield path


def read_text(path):
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


def check_text_files(root):
    errors = []
    for path in repo_files(root):
        text = read_text(path)
        if text is None:
            continue
        if LOCAL_PATH.search(text):
            errors.append(f"{path}: contains a local path")
        if path.suffix == ".json":
            try:
                json.loads(text)
            except json.JSONDecodeError as error:
                errors.append(f"{path}: invalid JSON: {error}")
    return errors


def version_key(snapshot):
    return [int(part) for part in re.findall(r"\d+", snapshot.name)]


def check_atlas(pet):
    try:
        manifest = json.loads((pet / "pet.json").read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    expected = (
        ATLAS_WIDTH,
        ATLAS_HEIGHT_BY_SPRITE_VERSION.get(manifest.get("spriteVersionNumber", 1)),
    )
    with Image.open(pet / "spritesheet.webp") as atlas:
        if atlas.size != expected:
            return [f"{pet}: atlas size {atlas.size} does not match {expected}"]
    return []


def check_newest_snapshot(pet):
    snapshots = sorted(
        (path for path in (pet / "versions").glob("*") if path.is_dir()),
        key=version_key,
    )
    if not snapshots:
        return [f"{pet}: no version snapshots"]
    newest = snapshots[-1]
    return [
        f"{pet}: {name} differs from newest snapshot {newest.name}"
        for name in ("pet.json", "spritesheet.webp")
        if (pet / name).read_bytes() != (newest / name).read_bytes()
    ]


def check_frame_references(pet):
    errors = []
    for snapshot in (pet / "versions").glob("*"):
        for path in snapshot.glob("qa/*.json"):
            for reference in FRAME_REFERENCE.findall(path.read_text(encoding="utf-8")):
                if not (snapshot / reference).exists():
                    errors.append(f"{path}: missing frame {reference}")
    return errors


def check_repository(root):
    errors = check_text_files(root)
    for pet in sorted((root / "pets").glob("*")):
        if pet.is_dir():
            errors += check_atlas(pet)
            errors += check_newest_snapshot(pet)
            errors += check_frame_references(pet)
    return errors


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    errors = check_repository(root)
    for error in errors:
        print(error)
    pets = [path for path in (root / "pets").glob("*") if path.is_dir()]
    print(f"Checked {len(pets)} pet(s): {len(errors)} problem(s).")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
