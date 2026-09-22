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
from archotraz.processor import EpistemicallyBoundedProcessor
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

    def test_parser_exposes_process_features_without_authority_options(self) -> None:
        parser = build_parser()
        subparsers = next(
            action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
        )
        self.assertIn("process-features", subparsers.choices)
        processor_parser = subparsers.choices["process-features"]
        option_strings = {option for action in processor_parser._actions for option in action.option_strings}
        for forbidden in ("--block", "--place", "--move", "--score", "--rank", "--guard", "--recommend", "--admit", "--reject"):
            self.assertNotIn(forbidden, option_strings)

    def test_process_features_cli_returns_partial_pre_intake_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "state" / "archotraz.db"
            ledger = EvidenceLedger(db)
            ledger.initialize()
            ManualRepositoryIngestor(ledger, dry_mode=True).ingest(
                REPO_URL,
                priority="research",
                tags=("evidence",),
                desired_block="C",
            )

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(["process-features", REPO_ID, "--db", str(db)])

            self.assertEqual(code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["processor"], "epistemically_bounded_feature_extraction")
            self.assertEqual(payload["evidence_scope"], "pre_intake")
            self.assertEqual(payload["completeness"], "partial")
            self.assertEqual(payload["features"]["provider"]["value"], "github")
            self.assertEqual(payload["features"]["mechanisms"]["state"], "unknown")
            self.assertIsNone(payload["features"]["mechanisms"]["value"])
            self.assertTrue(payload["missingness"]["mechanisms"])
            self.assertNotIn("desired_block", payload["features"])
            self.assertEqual(ledger.rows("decisions"), [])

    def test_parser_exposes_process_matrix_without_authority_options(self) -> None:
        parser = build_parser()
        subparsers = next(
            action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
        )
        self.assertIn("process-matrix", subparsers.choices)
        matrix_parser = subparsers.choices["process-matrix"]
        option_strings = {option for action in matrix_parser._actions for option in action.option_strings}
        for forbidden in ("--encode", "--impute", "--score", "--rank", "--classify", "--block", "--guard", "--recommend", "--admit", "--reject"):
            self.assertNotIn(forbidden, option_strings)

    def test_process_matrix_cli_projects_only_explicit_snapshot_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "state" / "archotraz.db"
            ledger = EvidenceLedger(db)
            ledger.initialize()
            ingestor = ManualRepositoryIngestor(ledger, dry_mode=True)
            processor = EpistemicallyBoundedProcessor(ledger)

            bravo = ingestor.ingest(
                "https://github.com/example/bravo",
                priority=None,
                tags=("bravo",),
            ).record.record_id
            alpha = ingestor.ingest(
                "https://github.com/example/alpha",
                priority="research",
                tags=("alpha",),
            ).record.record_id
            bravo_snapshot = processor.extract(bravo).observation_id
            alpha_snapshot = processor.extract(alpha).observation_id

            observations_before = len(
                [row for row in ledger.rows("observations") if row["kind"] == "processor.feature_snapshot"]
            )
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(
                    [
                        "process-matrix",
                        bravo_snapshot,
                        alpha_snapshot,
                        "--db",
                        str(db),
                    ]
                )

            self.assertEqual(code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["processor"], "epistemically_bounded_feature_matrix")
            self.assertEqual(payload["repo_record_ids"], [alpha, bravo])
            self.assertEqual(payload["source_snapshot_ids"], [alpha_snapshot, bravo_snapshot])
            mechanisms_index = payload["feature_names"].index("mechanisms")
            self.assertIsNone(payload["values"][0][mechanisms_index])
            self.assertTrue(payload["missingness"][0][mechanisms_index])
            self.assertEqual(
                len([row for row in ledger.rows("observations") if row["kind"] == "processor.feature_snapshot"]),
                observations_before,
            )
            self.assertEqual(ledger.rows("decisions"), [])

    def test_parser_exposes_process_encode_without_authority_options(self) -> None:
        parser = build_parser()
        subparsers = next(
            action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
        )
        self.assertIn("process-encode", subparsers.choices)
        encoding_parser = subparsers.choices["process-encode"]
        option_strings = {option for action in encoding_parser._actions for option in action.option_strings}
        for forbidden in ("--impute", "--weight", "--score", "--rank", "--classify", "--block", "--guard", "--recommend", "--admit", "--reject"):
            self.assertNotIn(forbidden, option_strings)

    def test_process_encode_cli_consumes_only_explicit_matrix_observation_id(self) -> None:
        from archotraz.processor_matrix import EpistemicallyBoundedMatrixBuilder

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "state" / "archotraz.db"
            ledger = EvidenceLedger(db)
            ledger.initialize()
            ingestor = ManualRepositoryIngestor(ledger, dry_mode=True)
            processor = EpistemicallyBoundedProcessor(ledger)

            alpha = ingestor.ingest(
                "https://github.com/example/alpha",
                priority="research",
                tags=("beta", "alpha"),
            ).record.record_id
            bravo = ingestor.ingest(
                "https://github.com/example/bravo",
                priority=None,
                tags=(),
            ).record.record_id
            alpha_snapshot = processor.extract(alpha).observation_id
            bravo_snapshot = processor.extract(bravo).observation_id
            matrix = EpistemicallyBoundedMatrixBuilder(ledger).build([bravo_snapshot, alpha_snapshot])

            matrices_before = len(
                [row for row in ledger.rows("observations") if row["kind"] == "processor.feature_matrix"]
            )
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(["process-encode", matrix.observation_id, "--db", str(db)])

            self.assertEqual(code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["processor"], "epistemically_bounded_categorical_encoding")
            self.assertEqual(payload["source_matrix_id"], matrix.observation_id)
            self.assertEqual(payload["encoded_features"], ["provider", "tags", "priority"])
            self.assertEqual(payload["vocabularies"]["provider"], ["github"])
            self.assertEqual(payload["vocabularies"]["tags"], ["alpha", "beta"])
            priority_columns = [
                index for index, name in enumerate(payload["encoded_feature_names"]) if name.startswith("priority::")
            ]
            self.assertTrue(priority_columns)
            bravo_row = payload["repo_record_ids"].index(bravo)
            self.assertTrue(all(payload["encoded_missingness"][bravo_row][index] for index in priority_columns))
            self.assertTrue(all(payload["encoded_values"][bravo_row][index] is None for index in priority_columns))
            self.assertEqual(
                len([row for row in ledger.rows("observations") if row["kind"] == "processor.feature_matrix"]),
                matrices_before,
            )
            self.assertEqual(ledger.rows("decisions"), [])


if __name__ == "__main__":
    unittest.main()
