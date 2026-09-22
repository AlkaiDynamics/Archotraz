from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from archotraz.cells import CellBlock, CellHousing, CellHousingError
from archotraz.evidence import EvidenceLedger
from archotraz.repositories import ManualRepositoryIngestor


REPO_URL = "https://github.com/AlkaiDynamics/Archotraz"
REPO_ID = "repo:github:alkaidynamics/archotraz"


class CellHousingTests(unittest.TestCase):
    def make_state(self, *, desired_block: str | None = None) -> tuple[EvidenceLedger, CellHousing]:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        ledger = EvidenceLedger(Path(tmp.name) / "ledger.db")
        ledger.initialize()
        ingestor = ManualRepositoryIngestor(ledger, dry_mode=True)
        ingestor.ingest(REPO_URL, desired_block=desired_block)
        return ledger, CellHousing(ledger)

    def test_record_decision_persists_canonical_decision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = EvidenceLedger(Path(tmp) / "ledger.db")
            ledger.initialize()
            ref = ledger.record_decision(
                "cell.placement",
                status="recorded",
                rationale="explicit placement",
                payload={"repo_record_id": REPO_ID, "version": 1},
            )

            row = ledger.rows("decisions")[0]
            self.assertEqual(ref.evidence_type, "decision")
            self.assertEqual(row["id"], ref.evidence_id)
            self.assertEqual(row["kind"], "cell.placement")
            self.assertEqual(row["status"], "recorded")
            self.assertEqual(row["rationale"], "explicit placement")
            self.assertEqual(json.loads(row["payload_json"])["version"], 1)

    def test_desired_block_does_not_auto_place_repository(self) -> None:
        ledger, housing = self.make_state(desired_block="C")

        self.assertIsNone(housing.current(REPO_ID))
        self.assertEqual(housing.history(REPO_ID), [])
        self.assertEqual(ledger.rows("decisions"), [])

    def test_nonexistent_repo_record_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = EvidenceLedger(Path(tmp) / "ledger.db")
            ledger.initialize()
            housing = CellHousing(ledger)

            with self.assertRaises(CellHousingError):
                housing.place(
                    "repo:github:missing/repo",
                    block=CellBlock.A,
                    cell_id="A-01",
                    rationale="manual placement",
                )

        self.assertEqual(ledger.rows("decisions"), [])

    def test_invalid_block_fails_closed(self) -> None:
        ledger, housing = self.make_state()

        with self.assertRaises(CellHousingError):
            housing.place(
                REPO_ID,
                block="NOT-A-BLOCK",
                cell_id="X-01",
                rationale="manual placement",
            )

        self.assertEqual(ledger.rows("decisions"), [])

    def test_first_placement_records_version_one(self) -> None:
        ledger, housing = self.make_state()

        placement = housing.place(
            REPO_ID,
            block=CellBlock.B,
            cell_id="B-01",
            rationale="explicit manual placement",
        )

        self.assertEqual(placement.repo_record_id, REPO_ID)
        self.assertEqual(placement.block, CellBlock.B)
        self.assertEqual(placement.cell_id, "B-01")
        self.assertEqual(placement.stage, "cell_housing")
        self.assertEqual(placement.eligibility, "eligible")
        self.assertEqual(placement.version, 1)
        self.assertEqual(placement.rationale, "explicit manual placement")
        self.assertEqual(len(placement.evidence_basis), 1)
        self.assertEqual(ledger.rows("decisions")[0]["kind"], "cell.placement")

    def test_move_preserves_history_and_updates_current(self) -> None:
        _, housing = self.make_state()
        first = housing.place(
            REPO_ID,
            block=CellBlock.A,
            cell_id="A-01",
            rationale="initial placement",
        )

        second = housing.move(
            REPO_ID,
            block=CellBlock.B,
            cell_id="B-03",
            rationale="new evidence changes placement",
        )

        self.assertEqual(first.version, 1)
        self.assertEqual(second.version, 2)
        self.assertEqual(second.block, CellBlock.B)
        self.assertEqual(second.cell_id, "B-03")
        self.assertEqual(housing.current(REPO_ID), second)
        self.assertEqual(housing.history(REPO_ID), [first, second])

    def test_second_initial_placement_requires_explicit_move(self) -> None:
        _, housing = self.make_state()
        housing.place(
            REPO_ID,
            block=CellBlock.A,
            cell_id="A-01",
            rationale="initial placement",
        )

        with self.assertRaises(CellHousingError):
            housing.place(
                REPO_ID,
                block=CellBlock.B,
                cell_id="B-01",
                rationale="must use move instead",
            )

    def test_cell_housing_decisions_are_state_only_not_scoring_or_analysis(self) -> None:
        ledger, housing = self.make_state()
        placement = housing.place(
            REPO_ID,
            block=CellBlock.GEN_POP,
            cell_id="GEN-01",
            rationale="explicit state placement",
        )

        payload = json.loads(ledger.rows("decisions")[0]["payload_json"])
        self.assertEqual(
            set(payload),
            {
                "repo_record_id",
                "block",
                "cell_id",
                "stage",
                "eligibility",
                "version",
                "evidence_basis",
            },
        )
        self.assertEqual(placement.stage, "cell_housing")
        for forbidden in ("score", "scoring", "analysis", "source", "rejection", "features", "processor"):
            self.assertNotIn(forbidden, payload)
        for forbidden_method in ("score", "analyze_source", "reject", "process"):
            self.assertFalse(hasattr(housing, forbidden_method))


if __name__ == "__main__":
    unittest.main()
