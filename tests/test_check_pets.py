# SPDX-License-Identifier: MIT
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_pets.py"
LOCAL_PATH = "/Us" + "ers/someone/output/frame.png"


def write_atlas(path, height):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (1536, height)).save(path, "WEBP", lossless=True)


def write_pet(root, version=2, height=2288):
    pet = root / "pets" / "demo"
    manifest = {"id": "demo", "spritesheetPath": "spritesheet.webp"}
    if version == 2:
        manifest["spriteVersionNumber"] = 2
    for folder in (pet, pet / "versions" / "v2.0.0"):
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "pet.json").write_text(json.dumps(manifest))
        write_atlas(folder / "spritesheet.webp", height)
    return pet


class CheckPetsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def run_check(self):
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(self.root)],
            capture_output=True,
            text=True,
        )

    def assert_fails_with(self, text):
        result = self.run_check()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(text, result.stdout)

    def test_repo_without_pets_passes(self):
        self.assertEqual(self.run_check().returncode, 0)

    def test_valid_v2_pet_passes(self):
        write_pet(self.root)
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_valid_v1_pet_passes(self):
        write_pet(self.root, version=1, height=1872)
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_invalid_json_fails(self):
        pet = write_pet(self.root)
        (pet / "qa.json").write_text("{not json")
        self.assert_fails_with("invalid JSON")

    def test_local_path_fails(self):
        pet = write_pet(self.root)
        (pet / "spec.md").write_text(f"See {LOCAL_PATH}\n")
        self.assert_fails_with("local path")

    def test_wrong_atlas_size_fails(self):
        write_pet(self.root, height=1872)
        self.assert_fails_with("atlas size")

    def test_root_package_differing_from_newest_snapshot_fails(self):
        pet = write_pet(self.root)
        write_atlas(pet / "versions" / "v3.0.0" / "spritesheet.webp", 2288)
        (pet / "versions" / "v3.0.0" / "pet.json").write_text("{}")
        self.assert_fails_with("newest snapshot")

    def test_versions_sort_numerically(self):
        pet = write_pet(self.root)
        old = pet / "versions" / "v10.0.0"
        (pet / "versions" / "v2.0.0").rename(old)
        write_atlas(pet / "versions" / "v9.0.0" / "spritesheet.webp", 1872)
        (pet / "versions" / "v9.0.0" / "pet.json").write_text("{}")
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_missing_frame_reference_fails(self):
        pet = write_pet(self.root)
        qa = pet / "versions" / "v2.0.0" / "qa"
        qa.mkdir()
        (qa / "review.json").write_text(json.dumps({"frame": "frames/idle/00.png"}))
        self.assert_fails_with("missing frame")

    def test_present_frame_reference_passes(self):
        pet = write_pet(self.root)
        snapshot = pet / "versions" / "v2.0.0"
        (snapshot / "qa").mkdir()
        (snapshot / "qa" / "review.json").write_text(
            json.dumps({"frame": "frames/idle/00.png"})
        )
        (snapshot / "frames" / "idle").mkdir(parents=True)
        (snapshot / "frames" / "idle" / "00.png").write_bytes(b"png")
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stdout)


if __name__ == "__main__":
    unittest.main()
