import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "package_wave22_evidence.py"
SPEC = importlib.util.spec_from_file_location("package_wave22_evidence", MODULE_PATH)
assert SPEC and SPEC.loader
bundle = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bundle)


class EvidenceBundleTests(unittest.TestCase):
    def _controls(self, root: Path):
        baseline = root / "baseline.json"
        scenarios = root / "scenarios.json"
        baseline.write_text(
            json.dumps({
                "version": "0.5.5a1",
                "sha256": "d241696f9404a2373ed02a7c7c0246fa11b4a52afaedc4e1b60a03de2b441861",
                "integration_mode": "APP13_INTERNAL_BOUND_R22_UNBOUND",
            }),
            encoding="utf-8",
        )
        scenarios.write_text(
            json.dumps({"profiles": {"CORE_UAT": [{"id": "CORE-007"}]}}),
            encoding="utf-8",
        )
        return baseline, scenarios

    def test_clean_evidence_is_packaged_with_manifest_and_sha(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "evidence"
            evidence.mkdir()
            (evidence / "CORE-007.txt").write_text("PASS operator evidence", encoding="utf-8")
            baseline, scenarios = self._controls(root)
            status = root / "status.json"
            status.write_text(
                json.dumps({"scenarios": [{"id": "CORE-007", "status": "PASS"}]}),
                encoding="utf-8",
            )
            output = root / "bundle.zip"

            result = bundle.package_evidence(
                evidence,
                output,
                baseline_path=baseline,
                scenarios_path=scenarios,
                status_path=status,
            )

            self.assertEqual(result["status"], "PASS")
            self.assertFalse(result["human_uat_signed"])
            self.assertTrue(output.exists())
            self.assertTrue(output.with_suffix(".zip.sha256").exists())
            with zipfile.ZipFile(output) as zf:
                names = set(zf.namelist())
                self.assertIn("evidence/CORE-007.txt", names)
                self.assertIn("control/EVIDENCE_MANIFEST.json", names)
                self.assertIn("control/EVIDENCE_GUARD.json", names)
                self.assertIn("control/WAVE22_UAT_STATUS.json", names)
                manifest = json.loads(zf.read("control/EVIDENCE_MANIFEST.json"))
                self.assertEqual(manifest["authority"], "EVIDENCE_ONLY_NOT_A_UAT_SIGNATURE")

    def test_secret_blocks_bundle_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "evidence"
            evidence.mkdir()
            (evidence / "capture.txt").write_text("api_key=abcdefghijklmnop", encoding="utf-8")
            baseline, scenarios = self._controls(root)
            with self.assertRaisesRegex(ValueError, "evidence guard blocked"):
                bundle.package_evidence(
                    evidence,
                    root / "bundle.zip",
                    baseline_path=baseline,
                    scenarios_path=scenarios,
                )

    def test_unknown_scenario_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "evidence"
            evidence.mkdir()
            (evidence / "note.txt").write_text("clean", encoding="utf-8")
            baseline, scenarios = self._controls(root)
            status = root / "status.json"
            status.write_text(
                json.dumps({"scenarios": [{"id": "CORE-999", "status": "PASS"}]}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "unknown scenario id"):
                bundle.package_evidence(
                    evidence,
                    root / "bundle.zip",
                    baseline_path=baseline,
                    scenarios_path=scenarios,
                    status_path=status,
                )

    def test_output_inside_evidence_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "evidence"
            evidence.mkdir()
            (evidence / "note.txt").write_text("clean", encoding="utf-8")
            baseline, scenarios = self._controls(root)
            with self.assertRaisesRegex(ValueError, "outside the evidence directory"):
                bundle.package_evidence(
                    evidence,
                    evidence / "bundle.zip",
                    baseline_path=baseline,
                    scenarios_path=scenarios,
                )


if __name__ == "__main__":
    unittest.main()
