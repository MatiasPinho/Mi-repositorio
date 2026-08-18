from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import illustration_figure


class IllustrationCredentialTests(unittest.TestCase):
    def test_environment_wins_over_local_env_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".env").write_text(
                "CLOUDFLARE_ACCOUNT_ID=file-account\nCLOUDFLARE_API_TOKEN=file-token\n",
                encoding="utf-8",
            )
            with mock.patch.object(illustration_figure, "ROOT", root), mock.patch.dict(
                os.environ,
                {"CLOUDFLARE_ACCOUNT_ID": "env-account", "CLOUDFLARE_API_TOKEN": "env-token"},
                clear=False,
            ):
                self.assertEqual(illustration_figure._credential("CLOUDFLARE_ACCOUNT_ID"), "env-account")
                self.assertEqual(illustration_figure._credential("CLOUDFLARE_API_TOKEN"), "env-token")

    def test_ignored_env_files_work_without_shell_exports(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".env").write_text(
                "# local only\nexport CLOUDFLARE_ACCOUNT_ID='file-account'\nCLOUDFLARE_API_TOKEN=\"file-token\"\n",
                encoding="utf-8",
            )
            clean = dict(os.environ)
            clean.pop("CLOUDFLARE_ACCOUNT_ID", None)
            clean.pop("CLOUDFLARE_API_TOKEN", None)
            with mock.patch.object(illustration_figure, "ROOT", root), mock.patch.dict(os.environ, clean, clear=True):
                self.assertEqual(illustration_figure._credential("CLOUDFLARE_ACCOUNT_ID"), "file-account")
                self.assertEqual(illustration_figure._credential("CLOUDFLARE_API_TOKEN"), "file-token")

    def test_example_exists_but_real_env_files_are_gitignored(self):
        root = Path(__file__).resolve().parents[1]
        example = (root / ".env.example").read_text(encoding="utf-8")
        ignore = (root / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn("CLOUDFLARE_ACCOUNT_ID=", example)
        self.assertIn("CLOUDFLARE_API_TOKEN=", example)
        self.assertIn(".env", ignore)
        self.assertIn(".env.local", ignore)


if __name__ == "__main__":
    unittest.main()
