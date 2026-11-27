import importlib
import sys
import types
import unittest
from unittest.mock import patch


class PublicLayoutTests(unittest.TestCase):
    def test_vlfd_ui_imports_sibling_electronic_keyboard_modules(self) -> None:
        pygame_stub = types.ModuleType("pygame")
        numpy_stub = types.ModuleType("numpy")
        sys.modules.pop("host.pc_keyboard.ui_vlfd", None)

        with patch.dict(sys.modules, {"pygame": pygame_stub, "numpy": numpy_stub}):
            module = importlib.import_module("host.pc_keyboard.ui_vlfd")

        self.assertTrue(hasattr(module, "VlfdMainWindow"))


if __name__ == "__main__":
    unittest.main()
