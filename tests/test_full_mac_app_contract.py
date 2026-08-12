import importlib.util
import json
import os
import plistlib
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
    def _bundle_fixture(self, root: Path) -> Path:
        bundle = root / "Binario Marketing IA.app"
        contents = bundle / "Contents"
        app13 = contents / "Resources" / "App13"
        runtime = contents / "Resources" / "runtime"
        macos = contents / "MacOS"
        (runtime / "bin").mkdir(parents=True)
        macos.mkdir(parents=True)
        app13.mkdir(parents=True)

        with (contents / "Info.plist").open("wb") as handle:
            plistlib.dump({
                "CFBundleIdentifier": bundle_audit.EXPECTED_BUNDLE_ID,
                "CFBundleShortVersionString": bundle_audit.EXPECTED_VERSION,
                "CFBundleExecutable": "binario-marketing",
            }, handle)

        launcher = macos / "binario-marketing"
        launcher.write_text(
            '#!/bin/bash\n'
            'RUNTIME="$CONTENTS/Resources/runtime"\n'
            'PYTHON="$RUNTIME/bin/python3"\n'
            'export PATH="$RUNTIME/bin:/usr/bin:/bin"\n'
            'unset PYTHONHOME PYTHONPATH\n'
            'export PYTHONNOUSERSITE=1\n'
            'export PYTHONDONTWRITEBYTECODE=1\n',
            encoding="utf-8",
        )
        os.chmod(launcher, 0o755)

        python_bin = runtime / "bin" / "python3"
        python_bin.write_text("fixture\n", encoding="utf-8")
        os.chmod(python_bin, 0o755)
        (runtime / "FULL_MAC_PYTHON_RUNTIME.json").write_text(
            json.dumps({
                "architecture": "arm64",
                "python_version": bundle_audit.EXPECTED_PYTHON_VERSION,
                "release": bundle_audit.EXPECTED_PYTHON_RELEASE,
                "schema": bundle_audit.EXPECTED_RUNTIME_SCHEMA,
                "source_asset": bundle_audit.EXPECTED_RUNTIME_BY_ARCH["arm64"]["source_asset"],
                "source_sha256": bundle_audit.EXPECTED_RUNTIME_BY_ARCH["arm64"]["source_sha256"],
                "upstream": "astral-sh/python-build-standalone",
            }),
            encoding="utf-8",
        )

        runner = app13 / "scripts" / "run_app13_uat_kit.sh"
        installer = app13 / "scripts" / "install_app13_uat_kit_macos.sh"
        runner.parent.mkdir(parents=True, exist_ok=True)
        runner.write_text("#!/bin/bash\n", encoding="utf-8")
        installer.write_text("#!/bin/bash\n", encoding="utf-8")
        os.chmod(runner, 0o755)
        os.chmod(installer, 0o755)
        for i in range(435):
            p = app13 / "payload" / f"entry_{i:03d}.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("{}\n", encoding="utf-8")
        return bundle

    def test_missing_bundle_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = bundle_audit.audit(Path(tmp) / "Missing.app")
            self.assertEqual(result["status"], "BLOCKED")

    def test_pinned_runtime_and_isolated_launcher_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = self._bundle_fixture(Path(tmp))
            result = bundle_audit.audit(bundle)
            self.assertEqual(result["status"], "PASS", result["problems"])

    def test_runtime_digest_drift_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = self._bundle_fixture(Path(tmp))
            manifest_path = bundle / "Contents" / "Resources" / "runtime" / "FULL_MAC_PYTHON_RUNTIME.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["source_sha256"] = "0" * 64
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result = bundle_audit.audit(bundle)
            self.assertEqual(result["status"], "BLOCKED")
            self.assertTrue(any("embedded CPython source SHA256 mismatch" in p for p in result["problems"]))


class FullMacRuntimeContractTests(unittest.TestCase):
    def test_runtime_pin_covers_both_mac_architectures(self):
        pins = (ROOT / "scripts/full_mac_python_runtime.env").read_text(encoding="utf-8")
        self.assertIn("FULL_MAC_PYTHON_VERSION='3.12.13'", pins)
        self.assertIn("FULL_MAC_PYTHON_RELEASE='20260807'", pins)
        self.assertIn("25baa97c65b3f0aa90e21131b4f9e80aef8899e8144006db8a9d2c1ab9e807e3", pins)
        self.assertIn("127053f1736f721e391ddb46f07585d05756e15bb8d757d3bbc0519738998ba1", pins)
        self.assertIn("aarch64-apple-darwin-install_only_stripped.tar.gz", pins)
        self.assertIn("x86_64-apple-darwin-install_only_stripped.tar.gz", pins)

    def test_bootstrap_verifies_archive_before_extraction(self):
        script = (ROOT / "scripts/bootstrap_full_mac_python.sh").read_text(encoding="utf-8")
        self.assertIn('/usr/bin/shasum -a 256 "$ARCHIVE"', script)
        self.assertIn('[[ "$ACTUAL_SHA256" == "$EXPECTED_SHA256" ]]', script)
        self.assertLess(script.index("ACTUAL_SHA256="), script.index('/usr/bin/tar -xzf "$ARCHIVE"'))
        self.assertIn('"$TARGET/bin/python3" -I -B', script)

    def test_builder_does_not_depend_on_host_python(self):
        script = (ROOT / "scripts/build_full_mac_app.sh").read_text(encoding="utf-8")
        self.assertIn("bootstrap_full_mac_python.sh", script)
        self.assertNotIn("BINARIO_EMBEDDED_PYTHON", script)
        self.assertNotIn("command -v python3", script)
        self.assertNotRegex(script, r"(?m)^[ \t]*python3(?:[ \t]|$)")
        self.assertIn('"$BUNDLE_PYTHON" -I -B scripts/audit_full_mac_bundle.py', script)

    def test_generated_launcher_isolates_python(self):
        script = (ROOT / "scripts/build_full_mac_app.sh").read_text(encoding="utf-8")
        self.assertIn('export PATH="\\$RUNTIME/bin:/usr/bin:/bin"', script)
        self.assertIn("unset PYTHONHOME PYTHONPATH", script)
        self.assertIn("export PYTHONNOUSERSITE=1", script)

    def test_importer_enforces_canonical_archive_name(self):
        script = (ROOT / "scripts/import_wave21_release.py").read_text(encoding="utf-8")
        self.assertIn("if archive.name != EXPECTED_NAME:", script)

    def test_ci_checks_native_arm64_and_x86_64_runtimes(self):
        workflow = (ROOT / ".github/workflows/full-mac-delivery.yml").read_text(encoding="utf-8")
        self.assertIn("runner: macos-15\n            arch: arm64", workflow)
        self.assertIn("runner: macos-15-intel\n            arch: x86_64", workflow)
        self.assertIn("Bootstrap pinned embedded CPython", workflow)


if __name__ == "__main__":
    unittest.main()
