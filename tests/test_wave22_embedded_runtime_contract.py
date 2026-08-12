import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Wave22EmbeddedRuntimeContractTests(unittest.TestCase):
    def test_uat_launcher_uses_pinned_runtime_not_host_python(self):
        launcher = (ROOT / "RUN_WAVE22_MAC_UAT.command").read_text(encoding="utf-8")
        self.assertIn("bootstrap_full_mac_python.sh", launcher)
        self.assertIn('PYTHON="$CONTROL_RUNTIME/bin/python3"', launcher)
        self.assertIn('export PATH="$CONTROL_RUNTIME/bin:/usr/bin:/bin"', launcher)
        self.assertNotIn("command -v python3", launcher)
        self.assertNotRegex(launcher, r"(?m)^[ \t]*python3(?:[ \t]|$)")

    def test_preflight_bootstraps_when_runtime_not_injected(self):
        preflight = (ROOT / "scripts/wave22_mac_preflight.sh").read_text(encoding="utf-8")
        self.assertIn('PYTHON_BIN="${WAVE22_PYTHON_BIN:-}"', preflight)
        self.assertIn("bootstrap_full_mac_python.sh", preflight)
        self.assertIn('/usr/bin/shasum -a 256 "$ARCHIVE"', preflight)
        self.assertNotIn("command -v python3", preflight)
        self.assertNotRegex(preflight, r"(?m)^[ \t]*python3(?:[ \t]|$)")


if __name__ == "__main__":
    unittest.main()
