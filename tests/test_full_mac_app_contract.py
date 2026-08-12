import importlib.util
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name, relative):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


payload_audit = load_module("audit_full_app_payload", "scripts/audit_full_app_payload.py")
bundle_audit = load_module("audit_full_mac_bundle", "scripts/audit_full_mac_bundle.py")


class FullMacPayloadAuditTests(unittest.TestCase):
    def _fixture(self, root: Path):
        app = root / "app"
        app.mkdir()
        provenance = root / "provenance.json"
        provenance.write_text(json.dumps({
            "version": payload_audit.EXPECTED_VERSION,
            "sha256": payload_audit.EXPECTED_SHA256,
            "zip_crc": "PASS",
            "members": 500,
        }), encoding="utf-8")

        paths = [
            "scripts/run_app13_uat_kit.sh",
            "scripts/install_app13_uat_kit_macos.sh",
            "backend/server.py",
            "frontend/index.html",
            "frontend/app.js",
            "native/keychain_helper.swift",
            "campaign/workspace.json",
            "content/workspace.json",
            "crm/customer_360.json",
            "inbox/handoff.json",
            "growth/runtime.json",
            "paid_media/runtime.json",
            "automation/runtime.json",
            "autopilot/runtime.json",
            "action_center/tasks.json",
            "system/diagnostics.json",
            "uat/acceptance.json",
            "release/rollback.json",
        ]
        for rel in paths:
            p = app / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("fixture\n", encoding="utf-8")
        for rel in ("scripts/run_app13_uat_kit.sh", "scripts/install_app13_uat_kit_macos.sh"):
            os.chmod(app / rel, 0o755)
        for i in range(437 - len(paths)):
            p = app / "payload" / f"entry_{i:03d}.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("{}\n", encoding="utf-8")
        return app, provenance

    def test_complete_certified_shape_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            app, provenance = self._fixture(Path(tmp))
            result = payload_audit.audit(app, provenance)
            self.assertEqual(result["status"], "PASS", result["problems"])
            self.assertGreaterEqual(result["file_count"], 437)

    def test_partial_tree_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = root / "app"
            app.mkdir()
            (app / "server.py").write_text("pass\n", encoding="utf-8")
            provenance = root / "provenance.json"
            provenance.write_text(json.dumps({
                "version": payload_audit.EXPECTED_VERSION,
                "sha256": payload_audit.EXPECTED_SHA256,
                "zip_crc": "PASS",
                "members": 1,
            }), encoding="utf-8")
            result = payload_audit.audit(app, provenance)
            self.assertEqual(result["status"], "BLOCKED")
            self.assertTrue(any("incomplete" in p or "only" in p for p in result["problems"]))


class FullMacBundleAuditTests(unittest.TestCase):
    def test_missing_bundle_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = bundle_audit.audit(Path(tmp) / "Missing.app")
            self.assertEqual(result["status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
