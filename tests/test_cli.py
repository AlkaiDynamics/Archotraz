from __future__ import annotations

from contextlib import redirect_stdout
import argparse
import io
import json
import tempfile
import unittest
from pathlib import Path

from archotraz.cells import CellBlock, CellHousing
from archotraz.cli import build_parser, main
from archotraz.evidence import EvidenceLedger
from archotraz.repositories import ManualRepositoryIngestor


REPO_URL = "https://github.com/AlkaiDynamics/Archotraz"
REPO_ID = "repo:github:alkaidynamics/archotraz"


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
                        REPO_URL,
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
            self.assertEqual(payload["record"]["record_id"], REPO_ID)
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

    def test_place_cell_records_explicit_version_one(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "state" / "archotraz.db"
            ledger = EvidenceLedger(db)
            ledger.initialize()
            ManualRepositoryIngestor(ledger, dry_mode=True).ingest(REPO_URL)

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(
                    [
                        "place-cell",
                        REPO_ID,
                        "--db",
                        str(db),
                        "--block",
                        "B",
                        "--cell",
                        "B-01",
                        "--rationale",
                        "explicit CLI placement",
                    ]
                )

            self.assertEqual(code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["placement"]["block"], "B")
            self.assertEqual(payload["placement"]["cell_id"], "B-01")
            self.assertEqual(payload["placement"]["version"], 1)

    def test_cell_current_returns_current_placement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "state" / "archotraz.db"
            ledger = EvidenceLedger(db)
            ledger.initialize()
            ManualRepositoryIngestor(ledger, dry_mode=True).ingest(REPO_URL)
            CellHousing(ledger).place(
                REPO_ID,
                block=CellBlock.A,
                cell_id="A-01",
                rationale="domain setup",
            )

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(["cell-current", REPO_ID, "--db", str(db)])

            self.assertEqual(code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["placement"]["block"], "A")
            self.assertEqual(payload["placement"]["version"], 1)

    def test_cell_history_returns_all_versions_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "state" / "archotraz.db"
            ledger = EvidenceLedger(db)
            ledger.initialize()
            ManualRepositoryIngestor(ledger, dry_mode=True).ingest(REPO_URL)
            housing = CellHousing(ledger)
            housing.place(
                REPO_ID,
                block=CellBlock.A,
                cell_id="A-01",
                rationale="initial",
            )
            housing.move(
                REPO_ID,
                block=CellBlock.C,
                cell_id="C-02",
                rationale="explicit move",
            )

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(["cell-history", REPO_ID, "--db", str(db)])

            self.assertEqual(code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertTrue(payload["ok"])
            self.assertEqual([item["version"] for item in payload["history"]], [1, 2])
            self.assertEqual([item["block"] for item in payload["history"]], ["A", "C"])

    def test_parser_exposes_guard_pairs_without_scoring_options(self) -> None:
        parser = build_parser()
        subparsers = next(
            action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
        )
        self.assertIn("guard-pairs", subparsers.choices)
        guard_parser = subparsers.choices["guard-pairs"]
        option_strings = {option for action in guard_parser._actions for option in action.option_strings}
        for forbidden in ("--score", "--rank", "--best", "--threshold", "--block", "--auto-place", "--recommend"):
            self.assertNotIn(forbidden, option_strings)

    def test_guard_pairs_cli_returns_complete_unordered_universe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "state" / "archotraz.db"
            ledger = EvidenceLedger(db)
            ledger.initialize()
            ingestor = ManualRepositoryIngestor(ledger, dry_mode=True)
            housing = CellHousing(ledger)
            repo_ids = []
            for index, name in enumerate(("alpha", "bravo", "charlie")):
                result = ingestor.ingest(f"https://github.com/example/{name}")
                repo_ids.append(result.record.record_id)
                housing.place(
                    result.record.record_id,
                    block=("A", "B", "C")[index],
                    cell_id=f"CELL-{index + 1}",
                    rationale="explicit CLI test placement",
                )

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(["guard-pairs", *repo_ids, "--db", str(db)])

            self.assertEqual(code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["guard"], "matcher.exhaustive_pair_enumeration")
            self.assertEqual(payload["candidate_count"], 3)
            self.assertEqual(payload["pair_count"], 3)
            self.assertTrue(payload["complete_unordered_universe"])
            self.assertEqual(len(payload["pairs"]), 3)
            serialized = json.dumps(payload).lower()
            for forbidden in ("score", "rank", "best", "recommendation", "synergy", "compatibility"):
                self.assertNotIn(forbidden, serialized)


if __name__ == "__main__":
    unittest.main()
