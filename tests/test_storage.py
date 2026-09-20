from __future__ import annotations

import unittest
from pathlib import Path

from fiscal_engine.storage import storage_paths


class StoragePathsTests(unittest.TestCase):
    def test_platform_defaults_do_not_depend_on_repository_or_cwd(self) -> None:
        home = Path("/usuarios/ana")
        self.assertEqual(storage_paths(environ={}, platform="linux", home=home), (
            home / ".local/share/fiscal-checker",
            home / ".local/share/fiscal-checker/casos",
            home / ".local/share/fiscal-checker/relatorios",
        ))
        self.assertEqual(storage_paths(environ={}, platform="darwin", home=home)[0],
                         home / "Library/Application Support/Fiscal Checker")
        self.assertEqual(storage_paths(environ={}, platform="win32", home=home)[0],
                         home / "AppData/Local/Fiscal Checker")

    def test_admin_can_choose_a_shared_or_custom_root(self) -> None:
        self.assertEqual(storage_paths(environ={"FISCAL_DATA_ROOT": "/dados/fiscal"},
                                       platform="linux", home=Path("/usuarios/ana"))[1:],
                         (Path("/dados/fiscal/casos"), Path("/dados/fiscal/relatorios")))
        self.assertEqual(storage_paths(environ={"FISCAL_UPLOAD_ROOT": "/rede/casos"},
                                       platform="linux", home=Path("/usuarios/ana"))[1],
                         Path("/rede/casos"))
        with self.assertRaisesRegex(ValueError, "caminho absoluto"):
            storage_paths(environ={"FISCAL_DATA_ROOT": "dados/fiscal"},
                          platform="linux", home=Path("/usuarios/ana"))


if __name__ == "__main__":
    unittest.main()
