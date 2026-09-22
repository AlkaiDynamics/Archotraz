from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from archotraz.evidence import EvidenceLedger
from archotraz.processor import (
    EpistemicallyBoundedProcessor,
    FeatureState,
    ProcessorRunError,
)
from archotraz.repositories import ManualRepositoryIngestor


REPO_URL = "https://github.com/AlkaiDynamics/Archotraz"
REPO_ID = "repo:github:alkaidynamics/archotraz"
UNKNOWN_FEATURES = (
    "mechanisms",
    "targets",
    "have",
    "need",
    "DataModel",
    "AccessPattern",
    "fidelity",
    "debt",
)


class ProcessorTests(unittest.TestCase):
    def make_processor(self, root: str, *, priority: str | None = "research", desired_block: str | None = "B"):
        ledger = EvidenceLedger(Path(root) / "ledger.db")
        ledger.initialize()
        ingest = ManualRepositoryIngestor(ledger, dry_mode=True).ingest(
            REPO_URL,
            priority=priority,
            tags=("evidence", "processor"),
            desired_block=desired_block,
        )
        return EpistemicallyBoundedProcessor(ledger), ledger, ingest

    def test_unknown_repo_fails_closed_and_records_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = EvidenceLedger(Path(tmp) / "ledger.db")
            ledger.initialize()
            processor = EpistemicallyBoundedProcessor(ledger)

            with self.assertRaises(ProcessorRunError):
                processor.extract("repo:github:missing/repo")

            attempts = ledger.rows("attempts")
            self.assertEqual(len(attempts), 1)
            self.assertEqual(attempts[0]["kind"], "processor.feature_extraction")
            self.assertEqual(attempts[0]["status"], "failed")
            self.assertEqual(len(ledger.rows("failures")), 1)
            self.assertEqual(
                [row for row in ledger.rows("observations") if row["kind"] == "processor.feature_snapshot"],
                [],
            )

    def test_missing_detective_evidence_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = EvidenceLedger(Path(tmp) / "ledger.db")
            ledger.initialize()
            repo = ledger.record_observation(
                "repo.record",
                "manual_input",
                {
                    "record_id": REPO_ID,
                    "provider": "github",
                    "tags": ["evidence"],
                    "priority": "research",
                    "desired_block": "B",
                },
                external_ref=REPO_ID,
                interpretation_status="structured_input",
            )
            self.assertTrue(repo.evidence_id)

            with self.assertRaises(ProcessorRunError):
                EpistemicallyBoundedProcessor(ledger).extract(REPO_ID)

            self.assertEqual(ledger.rows("attempts")[0]["status"], "failed")
            self.assertEqual(len(ledger.rows("failures")), 1)

    def test_supported_evidence_is_normalized_and_pre_intake_is_partial(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            processor, _, _ = self.make_processor(tmp)
            snapshot = processor.extract(REPO_ID)

            self.assertEqual(snapshot.repo_record_id, REPO_ID)
            self.assertEqual(snapshot.evidence_scope, "pre_intake")
            self.assertEqual(snapshot.completeness, "partial")
            self.assertEqual(snapshot.feature("provider").state, FeatureState.OBSERVED)
            self.assertEqual(snapshot.feature("provider").value, "github")
            self.assertEqual(snapshot.feature("tags").state, FeatureState.DECLARED)
            self.assertEqual(snapshot.feature("tags").value, ("evidence", "processor"))
            self.assertEqual(snapshot.feature("priority").state, FeatureState.DECLARED)
            self.assertEqual(snapshot.feature("priority").value, "research")
            self.assertNotIn("desired_block", {feature.name for feature in snapshot.features})

    def test_unsupported_canonical_features_are_explicit_unknowns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            processor, _, _ = self.make_processor(tmp)
            snapshot = processor.extract(REPO_ID)

            for name in UNKNOWN_FEATURES:
                feature = snapshot.feature(name)
                self.assertEqual(feature.state, FeatureState.UNKNOWN)
                self.assertIsNone(feature.value)
                self.assertTrue(snapshot.missingness[name])

    def test_unknown_never_collapses_to_zero_false_or_empty_string(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            processor, _, _ = self.make_processor(tmp)
            snapshot = processor.extract(REPO_ID)

            for name in UNKNOWN_FEATURES:
                value = snapshot.feature(name).value
                self.assertIsNone(value)
                self.assertIsNot(value, False)
                self.assertNotEqual(value, 0)
                self.assertNotEqual(value, "")

    def test_exact_upstream_evidence_basis_is_retained(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            processor, _, ingest = self.make_processor(tmp)
            snapshot = processor.extract(REPO_ID)

            self.assertEqual(
                snapshot.evidence_basis,
                (ingest.record_evidence_id, ingest.detective_evidence_id),
            )
            self.assertEqual(snapshot.feature("provider").evidence_basis, (ingest.record_evidence_id,))
            self.assertEqual(snapshot.feature("tags").evidence_basis, (ingest.record_evidence_id,))
            self.assertEqual(snapshot.feature("priority").evidence_basis, (ingest.record_evidence_id,))
            for name in UNKNOWN_FEATURES:
                self.assertEqual(snapshot.feature(name).evidence_basis, ())

    def test_same_evidence_produces_same_normalized_feature_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            processor, _, _ = self.make_processor(tmp)
            first = processor.extract(REPO_ID)
            second = processor.extract(REPO_ID)

            self.assertEqual(first.normalized_payload(), second.normalized_payload())
            self.assertNotEqual(first.attempt_id, second.attempt_id)
            self.assertNotEqual(first.observation_id, second.observation_id)

    def test_success_records_attempt_snapshot_and_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            processor, ledger, ingest = self.make_processor(tmp)
            snapshot = processor.extract(REPO_ID)

            attempts = ledger.rows("attempts")
            processor_attempt = attempts[-1]
            self.assertEqual(processor_attempt["kind"], "processor.feature_extraction")
            self.assertEqual(processor_attempt["status"], "succeeded")
            self.assertEqual(processor_attempt["id"], snapshot.attempt_id)

            snapshots = [row for row in ledger.rows("observations") if row["kind"] == "processor.feature_snapshot"]
            self.assertEqual(len(snapshots), 1)
            self.assertEqual(snapshots[0]["id"], snapshot.observation_id)

            provenance = [
                row
                for row in ledger.rows("provenance")
                if row["evidence_type"] == "observation" and row["evidence_id"] == snapshot.observation_id
            ]
            self.assertEqual(
                {row["source_ref"] for row in provenance},
                {ingest.record_evidence_id, ingest.detective_evidence_id},
            )

    def test_processor_creates_no_decisions_or_cell_placements(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            processor, ledger, _ = self.make_processor(tmp)
            before = list(ledger.rows("decisions"))
            processor.extract(REPO_ID)
            self.assertEqual(ledger.rows("decisions"), before)

    def test_processor_performs_no_network_requests(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            processor, _, _ = self.make_processor(tmp)
            with patch("urllib.request.urlopen", side_effect=AssertionError("network access forbidden")):
                snapshot = processor.extract(REPO_ID)
            self.assertEqual(snapshot.feature("provider").value, "github")

    def test_processor_does_not_read_repository_source_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            processor, _, _ = self.make_processor(tmp)
            with patch.object(Path, "read_text", side_effect=AssertionError("source read forbidden")), patch.object(
                Path, "read_bytes", side_effect=AssertionError("source read forbidden")
            ):
                snapshot = processor.extract(REPO_ID)
            self.assertEqual(snapshot.evidence_scope, "pre_intake")

    def test_output_contains_no_scoring_ranking_recommendation_or_admission_authority(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            processor, _, _ = self.make_processor(tmp)
            snapshot = processor.extract(REPO_ID)
            serialized = json.dumps(snapshot.normalized_payload(), sort_keys=True).lower()
            for forbidden in ("score", "rank", "recommend", "admit", "reject", "placement", "guard"):
                self.assertNotIn(forbidden, serialized)


if __name__ == "__main__":
    unittest.main()
