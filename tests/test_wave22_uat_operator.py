import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "wave22_uat_operator.py"
SPEC = importlib.util.spec_from_file_location("wave22_uat_operator", MODULE_PATH)
assert SPEC and SPEC.loader
operator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(operator)


def fresh_state():
    state = json.loads((ROOT / "docs" / "WAVE22_UAT_STATUS_TEMPLATE.json").read_text())
    return operator.normalize(state)


class Wave22UatOperatorTests(unittest.TestCase):
    def test_init_is_idempotent_and_atomic(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "evidence" / "status.json"
            template = ROOT / "docs" / "WAVE22_UAT_STATUS_TEMPLATE.json"
            first = operator.init_state(template, output)
            second = operator.init_state(template, output)
            self.assertTrue(output.is_file())
            self.assertEqual(first["created_at_utc"], second["created_at_utc"])
            self.assertEqual(len(second["events"]), 1)

    def test_fail_requires_open_defect_for_same_scenario(self):
        state = fresh_state()
        with self.assertRaises(ValueError):
            operator.record_scenario(
                state,
                scenario_id="CORE-007",
                result="FAIL",
                evidence_ref="evidence/core007.txt",
                note="workflow failed",
                actor="operator-a",
            )
        operator.open_defect(
            state,
            defect_id="W22-001",
            severity="P1",
            scenario_id="CORE-007",
            summary="Cannot complete CRM handoff",
            actor="operator-a",
        )
        operator.record_scenario(
            state,
            scenario_id="CORE-007",
            result="FAIL",
            evidence_ref="evidence/core007.txt",
            note="workflow failed reproducibly",
            actor="operator-a",
            defect_id="W22-001",
        )
        self.assertEqual(state["scenarios"][0]["status"], "FAIL")
        self.assertEqual(state["defects"]["open_p1"], 1)

    def test_verified_defect_recomputes_counts(self):
        state = fresh_state()
        operator.open_defect(state, defect_id="W22-002", severity="P2", scenario_id="CORE-008", summary="Recovery text unclear", actor="operator-a")
        self.assertEqual(state["defects"]["open_p2"], 1)
        operator.close_defect(state, defect_id="W22-002", resolution="Copy corrected", evidence_ref="evidence/retest.txt", actor="developer-b")
        self.assertEqual(state["defects"]["open_p2"], 0)
        self.assertEqual(state["defect_records"][0]["status"], "VERIFIED")

    def _pass_core(self, state, actor="operator-a"):
        for sid in operator.CORE_IDS:
            operator.record_scenario(
                state,
                scenario_id=sid,
                result="PASS",
                evidence_ref=f"evidence/{sid}.json",
                note=f"{sid} completed",
                actor=actor,
            )

    def test_signer_must_be_independent(self):
        state = fresh_state()
        self._pass_core(state)
        with self.assertRaises(ValueError):
            operator.sign_profile(state, profile="core", actor="operator-a")
        operator.sign_profile(state, profile="core", actor="reviewer-b")
        self.assertEqual(state["signoff"]["core_uat"], "SIGNED")
        self.assertEqual(state["signoff"]["core_uat_signature"]["actor"], "reviewer-b")

    def test_open_p0_blocks_signature(self):
        state = fresh_state()
        self._pass_core(state)
        operator.open_defect(state, defect_id="W22-003", severity="P0", scenario_id="CORE-009", summary="Safety bypass", actor="operator-a")
        with self.assertRaises(ValueError):
            operator.sign_profile(state, profile="core", actor="reviewer-b")

    def test_open_p2_requires_rationale(self):
        state = fresh_state()
        self._pass_core(state)
        operator.open_defect(state, defect_id="W22-004", severity="P2", scenario_id="CORE-008", summary="Minor wording", actor="operator-a")
        with self.assertRaises(ValueError):
            operator.sign_profile(state, profile="core", actor="reviewer-b")
        operator.sign_profile(state, profile="core", actor="reviewer-b", rationale="Cosmetic wording does not block operator recovery; tracked for follow-up.")
        sig = state["signoff"]["core_uat_signature"]
        self.assertEqual(sig["residual_p2_p3"], 1)
        self.assertTrue(sig["risk_acceptance_rationale"])

    def test_rerecord_invalidates_existing_signature(self):
        state = fresh_state()
        self._pass_core(state)
        operator.sign_profile(state, profile="core", actor="reviewer-b")
        operator.record_scenario(state, scenario_id="CORE-007", result="PASS", evidence_ref="evidence/CORE-007-retest.json", note="fresh retest", actor="operator-c")
        self.assertEqual(state["signoff"]["core_uat"], "NOT_SIGNED")
        self.assertIsNone(state["signoff"]["core_uat_signature"])


if __name__ == "__main__":
    unittest.main()
