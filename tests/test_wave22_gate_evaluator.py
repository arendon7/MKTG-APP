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
    def _status(self, root: Path, *, pass_core=False, pass_mac=False, sign_core=False, sign_mac=False) -> Path:
        path = root / "status.json"
        scenarios = []
        for sid in gate.ALL_IDS:
            passed = (sid in gate.CORE_IDS and pass_core) or (sid in gate.MAC_IDS and pass_mac)
            scenarios.append({
                "id": sid,
                "status": "PASS" if passed else "NOT_RUN",
                "evidence_ref": f"evidence/{sid}.json" if passed else None,
                "operator_note": f"{sid} completed" if passed else None,
                "operator": "operator-core" if sid in gate.CORE_IDS and passed else ("operator-mac" if passed else None),
                "recorded_at_utc": "2026-08-12T02:00:00+00:00" if passed else None,
                "defect_id": None,
            })
        by_id = {item["id"]: item for item in scenarios}
        signoff = {
            "core_uat": "SIGNED" if sign_core else "NOT_SIGNED",
            "standalone_mac_uat": "SIGNED" if sign_mac else "NOT_SIGNED",
            "core_uat_signature": None,
            "standalone_mac_uat_signature": None,
        }
        if sign_core:
            signoff["core_uat_signature"] = {
                "actor": "reviewer-core",
                "signed_at_utc": "2026-08-12T02:10:00+00:00",
                "scenario_evidence": {sid: by_id[sid]["evidence_ref"] for sid in gate.CORE_IDS},
                "residual_p2_p3": 0,
                "risk_acceptance_rationale": None,
            }
        if sign_mac:
            signoff["standalone_mac_uat_signature"] = {
                "actor": "reviewer-mac",
                "signed_at_utc": "2026-08-12T02:20:00+00:00",
                "scenario_evidence": {sid: by_id[sid]["evidence_ref"] for sid in gate.MAC_IDS},
                "residual_p2_p3": 0,
                "risk_acceptance_rationale": None,
            }
        path.write_text(json.dumps({
            "baseline": {"version": gate.EXPECTED_VERSION, "sha256": gate.EXPECTED_SHA256},
            "scenarios": scenarios,
            "defects": {"open_p0": 0, "open_p1": 0, "open_p2": 0, "open_p3": 0},
            "defect_records": [],
            "external_gates": {"r22": "PHYSICALLY_UNBOUND", "live_providers": "BLOCKED"},
            "signoff": signoff,
        }), encoding="utf-8")
        return path

    def _provenance(self, root: Path) -> tuple[Path, Path]:
        app = root / "app"; app.mkdir()
        provenance = root / "provenance.json"
        provenance.write_text(json.dumps({"version": gate.EXPECTED_VERSION, "sha256": gate.EXPECTED_SHA256, "zip_crc": "PASS"}), encoding="utf-8")
        return provenance, app

    def test_missing_source_points_to_exact_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = gate.evaluate(root / "missing.json", root / "missing-status.json", root / "app")
            self.assertEqual(result["next_gate"], "IMPORT_EXACT_WAVE21")
            self.assertEqual(result["source_import"], "MISSING")

    def test_imported_source_points_to_core_uat(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); provenance, app = self._provenance(root); status = self._status(root)
            result = gate.evaluate(provenance, status, app)
            self.assertEqual(result["next_gate"], "CORE_UAT")
            self.assertEqual(result["source_import"], "PASS")

    def test_structured_core_signature_points_to_mac_uat(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); provenance, app = self._provenance(root)
            status = self._status(root, pass_core=True, sign_core=True)
            result = gate.evaluate(provenance, status, app)
            self.assertEqual(result["core_uat"]["state"], "PASS")
            self.assertTrue(result["core_uat"]["signature_valid"])
            self.assertEqual(result["next_gate"], "STANDALONE_MAC_UAT")

    def test_all_human_gates_pass_points_to_r22(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); provenance, app = self._provenance(root)
            status = self._status(root, pass_core=True, pass_mac=True, sign_core=True, sign_mac=True)
            result = gate.evaluate(provenance, status, app)
            self.assertEqual(result["overall"], "WAVE22_GATE_PASSED")
            self.assertEqual(result["next_gate"], "BINARIO_R22_UAT")

    def test_plain_signed_string_without_signature_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); provenance, app = self._provenance(root)
            status = self._status(root, pass_core=True)
            payload = json.loads(status.read_text())
            payload["signoff"]["core_uat"] = "SIGNED"
            status.write_text(json.dumps(payload), encoding="utf-8")
            result = gate.evaluate(provenance, status, app)
            self.assertEqual(result["overall"], "BLOCKED")
            self.assertEqual(result["next_gate"], "CONTROL_POLICY_REPAIR")

    def test_stale_signature_evidence_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); provenance, app = self._provenance(root)
            status = self._status(root, pass_core=True, sign_core=True)
            payload = json.loads(status.read_text())
            payload["scenarios"][0]["evidence_ref"] = "evidence/new-retest.json"
            status.write_text(json.dumps(payload), encoding="utf-8")
            result = gate.evaluate(provenance, status, app)
            self.assertEqual(result["overall"], "BLOCKED")
            self.assertTrue(any("evidence no longer matches" in p for p in result["problems"]))

    def test_non_independent_signer_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); provenance, app = self._provenance(root)
            status = self._status(root, pass_core=True, sign_core=True)
            payload = json.loads(status.read_text())
            payload["signoff"]["core_uat_signature"]["actor"] = "operator-core"
            status.write_text(json.dumps(payload), encoding="utf-8")
            result = gate.evaluate(provenance, status, app)
            self.assertEqual(result["overall"], "BLOCKED")
            self.assertTrue(any("not independent" in p for p in result["problems"]))

    def test_r22_binding_during_wave22_is_policy_violation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); provenance, app = self._provenance(root); status = self._status(root)
            payload = json.loads(status.read_text()); payload["external_gates"]["r22"] = "BOUND"
            status.write_text(json.dumps(payload), encoding="utf-8")
            result = gate.evaluate(provenance, status, app)
            self.assertEqual(result["overall"], "BLOCKED")
            self.assertEqual(result["next_gate"], "CONTROL_POLICY_REPAIR")


if __name__ == "__main__":
    unittest.main()
