from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from tools.validate_sources import validate_python


class SourceValidationTests(unittest.TestCase):
    def test_python_validation_compiles_without_writing_bytecode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "valid.py"
            path.write_text("value = 1\n", encoding="utf-8")
            self.assertEqual(validate_python(path), (1, 0))
            self.assertFalse((path.parent / "__pycache__").exists())

    def test_detects_runtime_sys_path_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "bad.py"
            path.write_text("import sys\nsys.path.insert(0, 'scripts')\n", encoding="utf-8")
            self.assertEqual(validate_python(path), (1, 1))


if __name__ == "__main__":
    unittest.main()
