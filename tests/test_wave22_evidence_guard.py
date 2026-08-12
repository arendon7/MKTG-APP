import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "wave22_evidence_guard.py"
SPEC = importlib.util.spec_from_file_location("wave22_evidence_guard", MODULE_PATH)
assert SPEC and SPEC.loader
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


class EvidenceGuardTests(unittest.TestCase):
    def test_clean_evidence_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "CORE-007.txt").write_text("PASS: operator completed workflow", encoding="utf-8")
            result = guard.inspect(root)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["file_count"], 1)

    def test_api_key_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "log.txt").write_text("api_key=abcdefghijklmnop", encoding="utf-8")
            result = guard.inspect(root)
            self.assertEqual(result["status"], "BLOCKED")
            self.assertIn("api_key", result["findings"][0]["findings"])

    def test_private_key_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "capture.txt").write_text("-----BEGIN PRIVATE KEY-----\nabc", encoding="utf-8")
            result = guard.inspect(root)
            self.assertEqual(result["status"], "BLOCKED")

    def test_risky_filename_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".env").write_text("SAFE_PLACEHOLDER=true", encoding="utf-8")
            result = guard.inspect(root)
            self.assertEqual(result["status"], "BLOCKED")
            self.assertIn("risky_filename", result["findings"][0]["findings"])


if __name__ == "__main__":
    unittest.main()
