import importlib.util
import stat
import unittest
import zipfile
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "import_wave21_release.py"
SPEC = importlib.util.spec_from_file_location("wave21_import", MODULE_PATH)
assert SPEC and SPEC.loader
wave21_import = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(wave21_import)


class Wave21ImportGuardTests(unittest.TestCase):
    def info(self, name: str, mode: int = stat.S_IFREG | 0o644) -> zipfile.ZipInfo:
        item = zipfile.ZipInfo(name)
        item.create_system = 3
        item.external_attr = mode << 16
        return item

    def test_accepts_normal_source_path(self):
        path = wave21_import.validate_member(self.info("scripts/run.sh", stat.S_IFREG | 0o755))
        self.assertEqual(str(path), "scripts/run.sh")

    def test_rejects_parent_traversal(self):
        with self.assertRaises(ValueError):
            wave21_import.validate_member(self.info("../escape.txt"))

    def test_rejects_absolute_path(self):
        with self.assertRaises(ValueError):
            wave21_import.validate_member(self.info("/tmp/escape.txt"))

    def test_rejects_runtime_contamination(self):
        for name in ("pkg/__pycache__/x.pyc", "node_modules/x.js", "runtime/app.sqlite"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                wave21_import.validate_member(self.info(name))

    def test_rejects_symlink(self):
        with self.assertRaises(ValueError):
            wave21_import.validate_member(self.info("link", stat.S_IFLNK | 0o777))


if __name__ == "__main__":
    unittest.main()
