from __future__ import annotations

from contextlib import redirect_stdout
import argparse
import io
import json
import tempfile
import unittest
from pathlib import Path

from archotraz.cli import build_parser, main
from archotraz.evidence import EvidenceLedger


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

    def test_ingest_repo_runs_repo_record_event_and_detective(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "state" / "archotraz.db"
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(
                    [
                        "ingest-repo",
                        "https://github.com/AlkaiDynamics/Archotraz",
                        "--db",
                        str(db),
                        "--tag",
                        "evidence",
                        "--priority",
                        "research",
                        "--provenance-ref",
                        "cli:test",
                    ]
                )

            self.assertEqual(code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["created"])
            self.assertEqual(payload["record"]["record_id"], "repo:github:alkaidynamics/archotraz")
            self.assertIsNotNone(payload["ingested_evidence_id"])
            self.assertIsNotNone(payload["detective_evidence_id"])

            ledger = EvidenceLedger(db)
            kinds = [row["kind"] for row in ledger.rows("observations")]
            self.assertEqual(kinds, ["repo.record", "repo.ingested", "detective.triage"])

    def test_parser_exposes_cell_housing_commands(self) -> None:
        parser = build_parser()
        subparsers = next(
            action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
        )
        self.assertIn("place-cell", subparsers.choices)
        self.assertIn("cell-current", subparsers.choices)
        self.assertIn("cell-history", subparsers.choices)


if __name__ == "__main__":
    unittest.main()
