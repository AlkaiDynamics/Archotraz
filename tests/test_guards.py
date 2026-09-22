from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from archotraz.cells import CellBlock, CellHousing
from archotraz.evidence import EvidenceLedger
from archotraz.guards import GuardStatus, PairEligibilityGuard, PairUniverse
from archotraz.repos import RepoRegistry


class GuardTests(unittest.TestCase):
    def make_subjects(self, root: str):
        ledger = EvidenceLedger(Path(root) / "ledger.db")
        ledger.initialize()
        registry = RepoRegistry(ledger)
        housing = CellHousing(ledger=ledger, registry=registry)
        return ledger, registry, housing

    def test_pair_universe_is_complete_unordered_and_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, registry, _ = self.make_subjects(tmp)
            repos = [
                registry.add_manual("https://github.com/AlkaiDynamics/Archotraz").record,
                registry.add_manual("https://github.com/openai/openai-python").record,
                registry.add_manual("https://github.com/python/cpython").record,
            ]

            pairs = PairUniverse(registry).enumerate()

            self.assertEqual(len(pairs), 3)
            expected = {
                frozenset((repos[0].repo_id, repos[1].repo_id)),
                frozenset((repos[0].repo_id, repos[2].repo_id)),
                frozenset((repos[1].repo_id, repos[2].repo_id)),
            }
            actual = {frozenset((pair.repo_a_id, pair.repo_b_id)) for pair in pairs}
            self.assertEqual(actual, expected)
            self.assertEqual(
                [(pair.repo_a_id, pair.repo_b_id) for pair in pairs],
                sorted((pair.repo_a_id, pair.repo_b_id) for pair in pairs),
            )

    def test_pair_eligibility_is_unknown_until_both_candidates_have_explicit_cell_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, registry, housing = self.make_subjects(tmp)
            left = registry.add_manual("https://github.com/AlkaiDynamics/Archotraz").record
            right = registry.add_manual("https://github.com/openai/openai-python").record
            pair = PairUniverse(registry).enumerate()[0]
            guard = PairEligibilityGuard(registry=registry, housing=housing)

            before = guard.evaluate(pair)
            self.assertEqual(before.status, GuardStatus.UNKNOWN)
            self.assertEqual(
                set(before.missing),
                {
                    f"cell_assignment:{left.repo_id}",
                    f"cell_assignment:{right.repo_id}",
                },
            )

            housing.assign(left.repo_id, CellBlock.GEN_POP, source="manual", reason="test")
            housing.assign(right.repo_id, CellBlock.B, source="manual", reason="test")

            after = guard.evaluate(pair)
            self.assertEqual(after.status, GuardStatus.PASS)
            self.assertEqual(after.missing, ())
            self.assertEqual(len(after.evidence_used), 2)
            self.assertTrue(all(item.startswith("cell_assignment:") for item in after.evidence_used))

    def test_pair_eligibility_rejects_same_candidate_pair(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, registry, housing = self.make_subjects(tmp)
            repo = registry.add_manual("https://github.com/AlkaiDynamics/Archotraz").record
            guard = PairEligibilityGuard(registry=registry, housing=housing)

            result = guard.evaluate_ids(repo.repo_id, repo.repo_id)

            self.assertEqual(result.status, GuardStatus.FAIL)
            self.assertIn("distinct", result.findings[0].lower())


if __name__ == "__main__":
    unittest.main()
