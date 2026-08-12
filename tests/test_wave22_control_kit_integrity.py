import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "verify_wave22_control_kit.py"
SPEC = importlib.util.spec_from_file_location("verify_wave22_control_kit", MODULE_PATH)
assert SPEC and SPEC.loader
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


class ControlKitIntegrityTests(unittest.TestCase):
    def test_clean_manifest_verifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            script = root / "scripts" / "run.sh"
            script.write_text("#!/bin/bash\necho ok\n", encoding="utf-8")
            os.chmod(script, 0o755)
            (root / "README.md").write_text("Wave 22", encoding="utf-8")
            manifest = verifier.build_manifest(root, "abc123")
            path = root / "CONTROL_KIT_MANIFEST.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            result = verifier.verify(root, path)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["verified_files"], 2)

    def test_tampered_file_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            file = root / "README.md"
            file.write_text("original", encoding="utf-8")
            manifest = verifier.build_manifest(root, "abc123")
            path = root / "CONTROL_KIT_MANIFEST.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            file.write_text("tampered", encoding="utf-8")
            result = verifier.verify(root, path)
            self.assertEqual(result["status"], "BLOCKED")
            self.assertTrue(any("mismatch" in p for p in result["problems"]))

    def test_missing_executable_bit_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "run.command"
            script.write_text("#!/bin/bash\n", encoding="utf-8")
            os.chmod(script, 0o755)
            manifest = verifier.build_manifest(root, "abc123")
            path = root / "CONTROL_KIT_MANIFEST.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            os.chmod(script, 0o644)
            result = verifier.verify(root, path)
            self.assertEqual(result["status"], "BLOCKED")
            self.assertTrue(any("executable bit missing" in p for p in result["problems"]))

    def test_unsafe_manifest_path_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "CONTROL_KIT_MANIFEST.json"
            payload = {
                "schema": verifier.SCHEMA,
                "baseline_sha256": verifier.EXPECTED_BASELINE_SHA256,
                "control_plane_revision": "abc123",
                "files": [{"path": "../escape", "size": 1, "sha256": "x", "executable": False}],
            }
            path.write_text(json.dumps(payload), encoding="utf-8")
            result = verifier.verify(root, path)
            self.assertEqual(result["status"], "BLOCKED")
            self.assertTrue(any("unsafe manifest path" in p for p in result["problems"]))


if __name__ == "__main__":
    unittest.main()
