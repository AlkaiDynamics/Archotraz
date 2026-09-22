from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
import tempfile
import unittest
from pathlib import Path

from archotraz.cli import main


class CliTests(unittest.TestCase):
    def test_init_starts_archotraz_and_initializes_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "state" / "archotraz.db"
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(["init", "--db", str(db)])
            self.assertEqual(code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["dry_mode"])
            self.assertTrue(db.exists())

    def test_repo_add_cli_creates_then_deduplicates_repo_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "archotraz.db"

            first_stdout = io.StringIO()
            with redirect_stdout(first_stdout):
                first_code = main(
                    [
                        "repo",
                        "add",
                        "https://github.com/AlkaiDynamics/Archotraz",
                        "--db",
                        str(db),
                        "--priority",
                        "7",
                        "--tag",
                        "core",
                        "--note",
                        "manual intake",
                    ]
                )

            second_stdout = io.StringIO()
            with redirect_stdout(second_stdout):
                second_code = main(
                    [
                        "repo",
                        "add",
                        "https://github.com/alkaidynamics/archotraz.git",
                        "--db",
                        str(db),
                    ]
                )

            first = json.loads(first_stdout.getvalue())
            second = json.loads(second_stdout.getvalue())

            self.assertEqual(first_code, 0)
            self.assertEqual(second_code, 0)
            self.assertTrue(first["created"])
            self.assertFalse(second["created"])
            self.assertEqual(first["repo"]["repo_id"], second["repo"]["repo_id"])
            self.assertEqual(first["repo"]["canonical_url"], "https://github.com/AlkaiDynamics/Archotraz")
            self.assertEqual(first["repo"]["priority"], 7)
            self.assertEqual(first["repo"]["tags"], ["core"])
            self.assertEqual(first["repo"]["notes"], "manual intake")


if __name__ == "__main__":
    unittest.main()
