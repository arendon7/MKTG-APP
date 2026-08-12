from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("verify_wave22_contract", ROOT / "scripts" / "verify_wave22_contract.py")
assert SPEC is not None and SPEC.loader is not None
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


class Wave22ContractTests(unittest.TestCase):
    def _copy_contract_tree(self, dst: Path) -> None:
        (dst / "docs").mkdir(parents=True)
        (dst / "scripts").mkdir(parents=True)
        for rel in (
            "docs/BASELINE_WAVE21.json",
            "docs/WAVE22_UAT_SCENARIOS.json",
            "scripts/import_wave21_release.py",
        ):
            source = ROOT / rel
            target = dst / rel
            shutil.copy2(source, target)

    def test_current_repository_contract_passes(self) -> None:
        result = MOD.verify(ROOT)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["version"], "0.5.5a1")
        self.assertEqual(
            result["release_sha256"],
            "d241696f9404a2373ed02a7c7c0246fa11b4a52afaedc4e1b60a03de2b441861",
        )
        self.assertEqual(result["r22"], "PHYSICALLY_UNBOUND")

    def test_scenario_sha_drift_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._copy_contract_tree(root)
            path = root / "docs" / "WAVE22_UAT_SCENARIOS.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["baseline_sha256"] = "0" * 64
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(MOD.ContractError):
                MOD.verify(root)

    def test_importer_version_drift_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._copy_contract_tree(root)
            path = root / "scripts" / "import_wave21_release.py"
            text = path.read_text(encoding="utf-8")
            text = text.replace('EXPECTED_VERSION = "0.5.5a1"', 'EXPECTED_VERSION = "0.5.5a2"')
            path.write_text(text, encoding="utf-8")
            with self.assertRaises(MOD.ContractError):
                MOD.verify(root)

    def test_r22_binding_drift_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._copy_contract_tree(root)
            path = root / "docs" / "BASELINE_WAVE21.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["external_gates"]["r22"] = "BOUND"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(MOD.ContractError):
                MOD.verify(root)


if __name__ == "__main__":
    unittest.main()
