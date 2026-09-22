from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from archotraz.cells import CellHousing
from archotraz.evidence import EvidenceLedger
from archotraz.guards import GuardRunError, PairEnumerationGuard
from archotraz.repositories import ManualRepositoryIngestor


REPOS = (
    "https://github.com/example/alpha",
    "https://github.com/example/bravo",
    "https://github.com/example/charlie",
    "https://github.com/example/delta",
)
IDS = tuple(f"repo:github:example/{name}" for name in ("alpha", "bravo", "charlie", "delta"))


class PairEnumerationGuardTests(unittest.TestCase):
    def make_state(self, count: int = 4) -> tuple[EvidenceLedger, PairEnumerationGuard]:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        ledger = EvidenceLedger(Path(tmp.name) / "ledger.db")
        ledger.initialize()
        ingestor = ManualRepositoryIngestor(ledger, dry_mode=True)
        housing = CellHousing(ledger)
        for index, url in enumerate(REPOS[:count]):
            result = ingestor.ingest(url)
            housing.place(
                result.record.record_id,
                block=("A", "B", "C", "GEN-POP")[index],
                cell_id=f"CELL-{index + 1}",
                rationale="explicit test placement",
            )
        return ledger, PairEnumerationGuard(ledger)

    def test_contract_declares_guard_worker_boundary(self) -> None:
        _, guard = self.make_state(2)
        contract = guard.contract
        self.assertEqual(contract.family, "matcher")
        self.assertEqual(contract.algorithm, "exhaustive_unordered_pair_enumeration")
        self.assertTrue(contract.deterministic)
        self.assertFalse(contract.seed_required)
        self.assertIn("current CellPlacement", contract.consumes)
        self.assertIn("complete unordered pair proposals", contract.produces)
        self.assertIn("no scoring", contract.constraints)
        self.assertIn("no repository rejection", contract.constraints)

    def test_fewer_than_two_candidates_fails_closed_and_records_failure(self) -> None:
        ledger, guard = self.make_state(1)
        with self.assertRaises(GuardRunError):
            guard.run([IDS[0]])

        attempt = ledger.rows("attempts")[0]
        failure = ledger.rows("failures")[0]
        self.assertEqual(attempt["status"], "failed")
        self.assertEqual(attempt["kind"], "guard.matcher.exhaustive_pair_enumeration")
        self.assertEqual(failure["attempt_id"], attempt["id"])
        self.assertEqual(ledger.rows("decisions"), [ledger.rows("decisions")[0]])

    def test_unknown_repo_fails_closed(self) -> None:
        ledger, guard = self.make_state(2)
        decisions_before = list(ledger.rows("decisions"))
        with self.assertRaises(GuardRunError):
            guard.run([IDS[0], "repo:github:missing/repo"])
        self.assertEqual(ledger.rows("attempts")[0]["status"], "failed")
        self.assertEqual(ledger.rows("decisions"), decisions_before)

    def test_repo_without_explicit_current_cell_placement_fails_closed(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        ledger = EvidenceLedger(Path(tmp.name) / "ledger.db")
        ledger.initialize()
        ingestor = ManualRepositoryIngestor(ledger, dry_mode=True)
        first = ingestor.ingest(REPOS[0]).record.record_id
        second = ingestor.ingest(REPOS[1]).record.record_id
        CellHousing(ledger).place(first, block="A", cell_id="A-1", rationale="explicit")

        with self.assertRaises(GuardRunError):
            PairEnumerationGuard(ledger).run([first, second])

        self.assertEqual(ledger.rows("attempts")[0]["status"], "failed")
        self.assertEqual(len(ledger.rows("decisions")), 1)

    def test_duplicate_inputs_are_normalized_without_duplicate_pairs(self) -> None:
        _, guard = self.make_state(3)
        result = guard.run([IDS[0], IDS[1], IDS[0], IDS[2], IDS[1]])
        self.assertEqual(result.candidate_count, 3)
        self.assertEqual(result.pair_count, 3)
        self.assertEqual(len(result.pairs), 3)

    def test_n_candidates_produce_exact_complete_unordered_universe(self) -> None:
        _, guard = self.make_state(4)
        result = guard.run(list(IDS))
        self.assertEqual(result.pair_count, 6)
        self.assertEqual(result.pair_count, result.candidate_count * (result.candidate_count - 1) // 2)
        self.assertTrue(result.complete_unordered_universe)
        self.assertEqual(
            [(pair.left_repo_id, pair.right_repo_id) for pair in result.pairs],
            [
                (IDS[0], IDS[1]),
                (IDS[0], IDS[2]),
                (IDS[0], IDS[3]),
                (IDS[1], IDS[2]),
                (IDS[1], IDS[3]),
                (IDS[2], IDS[3]),
            ],
        )

    def test_input_order_does_not_change_pair_universe(self) -> None:
        _, guard = self.make_state(4)
        first = guard.run([IDS[3], IDS[0], IDS[2], IDS[1]])
        second = guard.run([IDS[1], IDS[2], IDS[0], IDS[3]])
        first_pairs = [(pair.left_repo_id, pair.right_repo_id) for pair in first.pairs]
        second_pairs = [(pair.left_repo_id, pair.right_repo_id) for pair in second.pairs]
        self.assertEqual(first_pairs, second_pairs)

    def test_pair_retains_current_placement_evidence_and_attempt_identity(self) -> None:
        ledger, guard = self.make_state(2)
        result = guard.run([IDS[0], IDS[1]])
        pair = result.pairs[0]
        placement_ids = {row["id"] for row in ledger.rows("decisions")}
        self.assertIn(pair.left_placement_decision_id, placement_ids)
        self.assertIn(pair.right_placement_decision_id, placement_ids)
        self.assertEqual(pair.attempt_id, result.attempt_id)
        self.assertEqual(pair.left_block, "A")
        self.assertEqual(pair.right_block, "B")

    def test_successful_run_persists_attempt_output_and_placement_provenance(self) -> None:
        ledger, guard = self.make_state(3)
        result = guard.run([IDS[0], IDS[1], IDS[2]])
        attempt = ledger.rows("attempts")[0]
        output = json.loads(attempt["output_json"])
        self.assertEqual(attempt["status"], "succeeded")
        self.assertEqual(output["pair_count"], 3)
        self.assertTrue(output["complete_unordered_universe"])

        provenance = [row for row in ledger.rows("provenance") if row["evidence_type"] == "attempt"]
        self.assertEqual(len(provenance), 3)
        self.assertEqual({row["evidence_id"] for row in provenance}, {result.attempt_id})
        current_decisions = {CellHousing(ledger).current(repo_id).decision_id for repo_id in IDS[:3]}
        self.assertEqual({row["source_ref"] for row in provenance}, current_decisions)

    def test_guard_run_does_not_create_or_move_cell_decisions(self) -> None:
        ledger, guard = self.make_state(3)
        before = list(ledger.rows("decisions"))
        guard.run([IDS[0], IDS[1], IDS[2]])
        self.assertEqual(ledger.rows("decisions"), before)

    def test_guard_output_contains_no_scores_rankings_or_recommendations(self) -> None:
        ledger, guard = self.make_state(3)
        result = guard.run([IDS[0], IDS[1], IDS[2]])
        output = json.loads(ledger.rows("attempts")[0]["output_json"])
        forbidden = {"score", "rank", "ranking", "best", "recommendation", "compatibility", "synergy", "promote", "reject"}
        serialized = json.dumps(output).lower()
        for term in forbidden:
            self.assertNotIn(term, serialized)
        for method in ("score", "rank", "recommend", "reject", "promote", "classify", "process"):
            self.assertFalse(hasattr(guard, method))
        self.assertEqual(result.contract.objective, "enumerate the complete unordered pair search universe")

    def test_dry_mode_does_not_block_non_mutating_guard_enumeration(self) -> None:
        _, guard = self.make_state(2)
        result = guard.run([IDS[0], IDS[1]])
        self.assertEqual(result.pair_count, 1)


if __name__ == "__main__":
    unittest.main()
