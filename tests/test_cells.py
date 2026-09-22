from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from archotraz.cells import CellBlock, CellHousing
from archotraz.evidence import EvidenceLedger
from archotraz.repos import RepoRegistry


class CellHousingTests(unittest.TestCase):
    def make_subject(self, root: str) -> tuple[CellHousing, RepoRegistry, EvidenceLedger]:
        ledger = EvidenceLedger(Path(root) / "ledger.db")
        ledger.initialize()
        registry = RepoRegistry(ledger)
        return CellHousing(ledger=ledger, registry=registry), registry, ledger

    def test_assignment_is_explicit_decision_and_preserves_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            housing, registry, ledger = self.make_subject(tmp)
            repo = registry.add_manual("https://github.com/AlkaiDynamics/Archotraz").record

            first = housing.assign(
                repo.repo_id,
                CellBlock.GEN_POP,
                source="manual",
                reason="initial operator placement",
            )
            second = housing.assign(
                repo.repo_id,
                CellBlock.B,
                source="manual",
                reason="later evidence justified balanced block",
            )

            current = housing.current(repo.repo_id)
            history = housing.history(repo.repo_id)

            self.assertEqual(current, second)
            self.assertEqual([item.block for item in history], [CellBlock.GEN_POP, CellBlock.B])
            self.assertIsNotNone(history[0].superseded_at)
            self.assertIsNone(history[1].superseded_at)
            self.assertNotEqual(first.assignment_id, second.assignment_id)

            decisions = ledger.rows("decisions")
            self.assertEqual([row["kind"] for row in decisions], ["cell.assignment", "cell.assignment"])
            self.assertEqual([row["status"] for row in decisions], ["applied", "applied"])

    def test_assignment_requires_reason_and_known_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            housing, registry, _ = self.make_subject(tmp)
            repo = registry.add_manual("https://github.com/AlkaiDynamics/Archotraz").record

            with self.assertRaises(ValueError):
                housing.assign(repo.repo_id, CellBlock.A, source="manual", reason="   ")

            with self.assertRaises(KeyError):
                housing.assign("missing-repo", CellBlock.A, source="manual", reason="test")

    def test_no_automatic_block_is_invented(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            housing, registry, _ = self.make_subject(tmp)
            repo = registry.add_manual("https://github.com/AlkaiDynamics/Archotraz").record

            self.assertIsNone(housing.current(repo.repo_id))


if __name__ == "__main__":
    unittest.main()
