from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from archotraz.cells import CellHousing
from archotraz.evidence import EvidenceLedger
from archotraz.guards import PairEnumerationGuard
from archotraz.processor import EpistemicallyBoundedProcessor
from archotraz.processor_matrix import (
    FEATURE_COLUMNS,
    EpistemicallyBoundedMatrixBuilder,
    MatrixRunError,
)


FEATURE_MATRIX_KIND = "processor.feature_matrix"
SNAPSHOT_KIND = "processor.feature_snapshot"


class ProcessorMatrixTests(unittest.TestCase):
    def make_ledger(self) -> EvidenceLedger:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        ledger = EvidenceLedger(Path(tmp.name) / "ledger.db")
        ledger.initialize()
        return ledger

    def add_snapshot(
        self,
        ledger: EvidenceLedger,
        repo_id: str,
        *,
        scope: str = "pre_intake",
        completeness: str = "partial",
        priority: str | None = "research",
        kind: str = SNAPSHOT_KIND,
        payload_override: object | None = None,
    ) -> str:
        if payload_override is None:
            features = {
                "provider": {
                    "value": "github",
                    "state": "observed",
                    "evidence_basis": [f"repo:{repo_id}"],
                },
                "tags": {
                    "value": ["evidence", repo_id.rsplit("/", 1)[-1]],
                    "state": "declared",
                    "evidence_basis": [f"repo:{repo_id}"],
                },
                "priority": {
                    "value": priority,
                    "state": "declared" if priority is not None else "unknown",
                    "evidence_basis": [f"repo:{repo_id}"] if priority is not None else [],
                },
            }
            for name in (
                "mechanisms",
                "targets",
                "have",
                "need",
                "DataModel",
                "AccessPattern",
                "fidelity",
                "debt",
            ):
                features[name] = {"value": None, "state": "unknown", "evidence_basis": []}
            missingness = {
                name: feature["state"] == "unknown"
                for name, feature in features.items()
            }
            payload: object = {
                "repo_record_id": repo_id,
                "evidence_scope": scope,
                "completeness": completeness,
                "features": features,
                "missingness": missingness,
                "evidence_basis": [f"repo:{repo_id}", f"detective:{repo_id}"],
            }
        else:
            payload = payload_override
        ref = ledger.record_observation(
            kind,
            "archotraz.processor",
            payload,
            external_ref=repo_id,
            interpretation_status="derived_normalization",
        )
        return ref.evidence_id

    def test_unknown_snapshot_id_fails_closed_and_records_no_partial_matrix(self) -> None:
        ledger = self.make_ledger()
        builder = EpistemicallyBoundedMatrixBuilder(ledger)

        with self.assertRaises(MatrixRunError):
            builder.build(["missing-snapshot"])

        self.assertEqual(ledger.rows("attempts")[0]["status"], "failed")
        self.assertEqual(len(ledger.rows("failures")), 1)
        self.assertEqual(
            [row for row in ledger.rows("observations") if row["kind"] == FEATURE_MATRIX_KIND],
            [],
        )

    def test_wrong_observation_kind_fails_closed(self) -> None:
        ledger = self.make_ledger()
        snapshot_id = self.add_snapshot(ledger, "repo:github:example/alpha", kind="detective.triage")

        with self.assertRaises(MatrixRunError):
            EpistemicallyBoundedMatrixBuilder(ledger).build([snapshot_id])

        self.assertEqual(ledger.rows("attempts")[0]["status"], "failed")

    def test_malformed_snapshot_payload_fails_closed(self) -> None:
        ledger = self.make_ledger()
        snapshot_id = self.add_snapshot(
            ledger,
            "repo:github:example/alpha",
            payload_override=["not", "a", "snapshot", "object"],
        )

        with self.assertRaises(MatrixRunError):
            EpistemicallyBoundedMatrixBuilder(ledger).build([snapshot_id])

        self.assertEqual(ledger.rows("attempts")[0]["status"], "failed")

    def test_multiple_snapshots_for_same_candidate_fail_closed(self) -> None:
        ledger = self.make_ledger()
        repo_id = "repo:github:example/alpha"
        first = self.add_snapshot(ledger, repo_id)
        second = self.add_snapshot(ledger, repo_id)

        with self.assertRaises(MatrixRunError):
            EpistemicallyBoundedMatrixBuilder(ledger).build([first, second])

        self.assertEqual(ledger.rows("attempts")[0]["status"], "failed")

    def test_mixed_evidence_scope_fails_closed(self) -> None:
        ledger = self.make_ledger()
        first = self.add_snapshot(ledger, "repo:github:example/alpha", scope="pre_intake")
        second = self.add_snapshot(ledger, "repo:github:example/bravo", scope="intake")

        with self.assertRaises(MatrixRunError):
            EpistemicallyBoundedMatrixBuilder(ledger).build([first, second])

    def test_mixed_completeness_fails_closed(self) -> None:
        ledger = self.make_ledger()
        first = self.add_snapshot(ledger, "repo:github:example/alpha", completeness="partial")
        second = self.add_snapshot(ledger, "repo:github:example/bravo", completeness="complete")

        with self.assertRaises(MatrixRunError):
            EpistemicallyBoundedMatrixBuilder(ledger).build([first, second])

    def test_schema_mismatch_fails_closed(self) -> None:
        ledger = self.make_ledger()
        snapshot_id = self.add_snapshot(ledger, "repo:github:example/alpha")
        row = next(row for row in ledger.rows("observations") if row["id"] == snapshot_id)
        payload = json.loads(row["payload_json"])
        payload["features"].pop("debt")
        bad = ledger.record_observation(
            SNAPSHOT_KIND,
            "archotraz.processor",
            payload,
            external_ref=payload["repo_record_id"],
            interpretation_status="derived_normalization",
        ).evidence_id

        with self.assertRaises(MatrixRunError):
            EpistemicallyBoundedMatrixBuilder(ledger).build([bad])

    def test_inconsistent_unknown_semantics_fail_closed(self) -> None:
        for mode in ("non_null_unknown", "unknown_marked_present"):
            with self.subTest(mode=mode):
                ledger = self.make_ledger()
                repo_id = f"repo:github:example/{mode}"
                good_id = self.add_snapshot(ledger, repo_id)
                row = next(row for row in ledger.rows("observations") if row["id"] == good_id)
                payload = json.loads(row["payload_json"])
                if mode == "non_null_unknown":
                    payload["features"]["mechanisms"]["value"] = 0
                else:
                    payload["missingness"]["mechanisms"] = False
                bad_id = ledger.record_observation(
                    SNAPSHOT_KIND,
                    "archotraz.processor",
                    payload,
                    external_ref=repo_id,
                    interpretation_status="derived_normalization",
                ).evidence_id
                with self.assertRaises(MatrixRunError):
                    EpistemicallyBoundedMatrixBuilder(ledger).build([bad_id])

    def test_input_order_does_not_change_canonical_matrix(self) -> None:
        ledger = self.make_ledger()
        bravo = self.add_snapshot(ledger, "repo:github:example/bravo", priority=None)
        alpha = self.add_snapshot(ledger, "repo:github:example/alpha", priority="research")
        builder = EpistemicallyBoundedMatrixBuilder(ledger)

        first = builder.build([bravo, alpha])
        second = builder.build([alpha, bravo])

        self.assertEqual(first.normalized_payload(), second.normalized_payload())
        self.assertEqual(
            first.repo_record_ids,
            ("repo:github:example/alpha", "repo:github:example/bravo"),
        )
        self.assertEqual(first.source_snapshot_ids, (alpha, bravo))

    def test_column_order_is_fixed_and_deterministic(self) -> None:
        ledger = self.make_ledger()
        snapshot_id = self.add_snapshot(ledger, "repo:github:example/alpha")
        result = EpistemicallyBoundedMatrixBuilder(ledger).build([snapshot_id])

        self.assertEqual(result.feature_names, FEATURE_COLUMNS)
        self.assertEqual(
            result.feature_names,
            (
                "provider",
                "tags",
                "priority",
                "mechanisms",
                "targets",
                "have",
                "need",
                "DataModel",
                "AccessPattern",
                "fidelity",
                "debt",
            ),
        )

    def test_unknown_projects_to_null_value_and_true_missingness(self) -> None:
        ledger = self.make_ledger()
        snapshot_id = self.add_snapshot(ledger, "repo:github:example/alpha", priority=None)
        result = EpistemicallyBoundedMatrixBuilder(ledger).build([snapshot_id])

        row = dict(zip(result.feature_names, result.values[0], strict=True))
        mask = dict(zip(result.feature_names, result.missingness[0], strict=True))
        self.assertIsNone(row["priority"])
        self.assertTrue(mask["priority"])
        self.assertIsNone(row["mechanisms"])
        self.assertTrue(mask["mechanisms"])
        self.assertNotEqual(row["mechanisms"], 0)
        self.assertIsNot(row["mechanisms"], False)
        self.assertNotEqual(row["mechanisms"], "")

    def test_known_values_are_retained_and_marked_present(self) -> None:
        ledger = self.make_ledger()
        snapshot_id = self.add_snapshot(ledger, "repo:github:example/alpha", priority="research")
        result = EpistemicallyBoundedMatrixBuilder(ledger).build([snapshot_id])

        row = dict(zip(result.feature_names, result.values[0], strict=True))
        mask = dict(zip(result.feature_names, result.missingness[0], strict=True))
        self.assertEqual(row["provider"], "github")
        self.assertEqual(row["tags"], ["evidence", "alpha"])
        self.assertEqual(row["priority"], "research")
        self.assertFalse(mask["provider"])
        self.assertFalse(mask["tags"])
        self.assertFalse(mask["priority"])

    def test_matrix_records_exact_source_snapshot_provenance(self) -> None:
        ledger = self.make_ledger()
        alpha = self.add_snapshot(ledger, "repo:github:example/alpha")
        bravo = self.add_snapshot(ledger, "repo:github:example/bravo")
        result = EpistemicallyBoundedMatrixBuilder(ledger).build([bravo, alpha])

        provenance = [
            row
            for row in ledger.rows("provenance")
            if row["evidence_type"] == "observation" and row["evidence_id"] == result.observation_id
        ]
        self.assertEqual({row["source_ref"] for row in provenance}, {alpha, bravo})
        self.assertEqual({row["source_type"] for row in provenance}, {"processor_feature_snapshot"})

    def test_success_records_attempt_and_matrix_observation(self) -> None:
        ledger = self.make_ledger()
        snapshot_id = self.add_snapshot(ledger, "repo:github:example/alpha")
        result = EpistemicallyBoundedMatrixBuilder(ledger).build([snapshot_id])

        attempt = ledger.rows("attempts")[0]
        self.assertEqual(attempt["kind"], "processor.feature_matrix_projection")
        self.assertEqual(attempt["status"], "succeeded")
        self.assertEqual(attempt["id"], result.attempt_id)
        observations = [row for row in ledger.rows("observations") if row["kind"] == FEATURE_MATRIX_KIND]
        self.assertEqual(len(observations), 1)
        self.assertEqual(observations[0]["id"], result.observation_id)

    def test_builder_has_no_acquisition_cell_guard_or_decision_authority(self) -> None:
        ledger = self.make_ledger()
        snapshot_id = self.add_snapshot(ledger, "repo:github:example/alpha")
        builder = EpistemicallyBoundedMatrixBuilder(ledger)
        decisions_before = list(ledger.rows("decisions"))

        with patch("urllib.request.urlopen", side_effect=AssertionError("network forbidden")), patch.object(
            Path, "read_text", side_effect=AssertionError("source read forbidden")
        ), patch.object(Path, "read_bytes", side_effect=AssertionError("source read forbidden")), patch.object(
            EpistemicallyBoundedProcessor, "extract", side_effect=AssertionError("feature extraction forbidden")
        ), patch.object(CellHousing, "current", side_effect=AssertionError("cell lookup forbidden")), patch.object(
            CellHousing, "place", side_effect=AssertionError("cell placement forbidden")
        ), patch.object(CellHousing, "move", side_effect=AssertionError("cell move forbidden")), patch.object(
            PairEnumerationGuard, "run", side_effect=AssertionError("guard execution forbidden")
        ):
            result = builder.build([snapshot_id])

        self.assertEqual(result.repo_record_ids, ("repo:github:example/alpha",))
        self.assertEqual(ledger.rows("decisions"), decisions_before)

    def test_matrix_output_has_no_scoring_ranking_classification_or_recommendation_authority(self) -> None:
        ledger = self.make_ledger()
        snapshot_id = self.add_snapshot(ledger, "repo:github:example/alpha")
        builder = EpistemicallyBoundedMatrixBuilder(ledger)
        result = builder.build([snapshot_id])
        serialized = json.dumps(result.normalized_payload(), sort_keys=True).lower()

        for forbidden in ("score", "rank", "classify", "recommend", "admit", "reject", "compatibility", "synergy"):
            self.assertNotIn(forbidden, serialized)
        for method in ("score", "rank", "classify", "recommend", "admit", "reject", "run_guard"):
            self.assertFalse(hasattr(builder, method))


if __name__ == "__main__":
    unittest.main()
