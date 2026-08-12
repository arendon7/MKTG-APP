import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "evaluate_wave22_gate.py"
SPEC = importlib.util.spec_from_file_location("evaluate_wave22_gate", MODULE_PATH)
assert SPEC and SPEC.loader
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


class GateEvaluatorTests(unittest.TestCase):
    def _status(self, root: Path, scenario_status="NOT_RUN", core_signoff="NOT_SIGNED", mac_signoff="NOT_SIGNED") -> Path:
        path = root / "status.json"
        ids = ["CORE-007", "CORE-008", "CORE-009", "MAC-001", "MAC-002", "MAC-003"]
        path.write_text(json.dumps({
            "baseline": {"version": gate.EXPECTED_VERSION, "sha256": gate.EXPECTED_SHA256},
            "scenarios": [{"id": item, "status": scenario_status} for item in ids],
            "defects": {"open_p0": 0, "open_p1": 0, "open_p2": 0, "open_p3": 0},
            "external_gates": {"r22": "PHYSICALLY_UNBOUND", "live_providers": "BLOCKED"},
            "signoff": {"core_uat": core_signoff, "standalone_mac_uat": mac_signoff},
        }), encoding="utf-8")
        return path

    def _provenance(self, root: Path) -> tuple[Path, Path]:
        app = root / "app"
        app.mkdir()
        provenance = root / "provenance.json"
        provenance.write_text(json.dumps({
            "version": gate.EXPECTED_VERSION,
            "sha256": gate.EXPECTED_SHA256,
            "zip_crc": "PASS",
        }), encoding="utf-8")
        return provenance, app

    def test_missing_source_points_to_exact_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = gate.evaluate(root / "missing.json", root / "missing-status.json", root / "app")
            self.assertEqual(result["next_gate"], "IMPORT_EXACT_WAVE21")
            self.assertEqual(result["source_import"], "MISSING")

    def test_imported_source_points_to_core_uat(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            provenance, app = self._provenance(root)
            status = self._status(root)
            result = gate.evaluate(provenance, status, app)
            self.assertEqual(result["next_gate"], "CORE_UAT")
            self.assertEqual(result["source_import"], "PASS")

    def test_core_pass_points_to_mac_uat(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            provenance, app = self._provenance(root)
            status = self._status(root, scenario_status="PASS", core_signoff="SIGNED", mac_signoff="NOT_SIGNED")
            result = gate.evaluate(provenance, status, app)
            self.assertEqual(result["core_uat"]["state"], "PASS")
            self.assertEqual(result["next_gate"], "STANDALONE_MAC_UAT")

    def test_all_human_gates_pass_points_to_r22(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            provenance, app = self._provenance(root)
            status = self._status(root, scenario_status="PASS", core_signoff="SIGNED", mac_signoff="SIGNED")
            result = gate.evaluate(provenance, status, app)
            self.assertEqual(result["overall"], "WAVE22_GATE_PASSED")
            self.assertEqual(result["next_gate"], "BINARIO_R22_UAT")

    def test_r22_binding_during_wave22_is_policy_violation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            provenance, app = self._provenance(root)
            status = self._status(root)
            payload = json.loads(status.read_text())
            payload["external_gates"]["r22"] = "BOUND"
            status.write_text(json.dumps(payload), encoding="utf-8")
            result = gate.evaluate(provenance, status, app)
            self.assertEqual(result["overall"], "BLOCKED")
            self.assertEqual(result["next_gate"], "CONTROL_POLICY_REPAIR")


if __name__ == "__main__":
    unittest.main()
