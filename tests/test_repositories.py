from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from archotraz.evidence import EvidenceLedger
from archotraz.repositories import (
    ManualRepositoryIngestor,
    RepositoryInputError,
    canonicalize_repository_url,
)


class RepositoryIngestTests(unittest.TestCase):
    def test_github_url_is_canonicalized(self) -> None:
        record_id, owner, name, canonical = canonicalize_repository_url(
            "https://www.github.com/AlkaiDynamics/Archotraz.git"
        )
        self.assertEqual(record_id, "repo:github:alkaidynamics/archotraz")
        self.assertEqual(owner, "alkaidynamics")
        self.assertEqual(name, "archotraz")
        self.assertEqual(canonical, "https://github.com/alkaidynamics/archotraz")

    def test_unsupported_provider_fails_closed(self) -> None:
        with self.assertRaises(RepositoryInputError):
            canonicalize_repository_url("https://example.com/owner/repo")

    def test_ingest_records_repo_event_provenance_and_non_rejecting_detective(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = EvidenceLedger(Path(tmp) / "ledger.db")
            ledger.initialize()
            ingestor = ManualRepositoryIngestor(ledger, dry_mode=True)

            result = ingestor.ingest(
                "https://github.com/AlkaiDynamics/Archotraz",
                priority="research",
                tags=("orchestration", "orchestration", " evidence "),
                desired_block="B",
                algorithm_overrides=("matcher-a",),
                guard_overrides=("validator-a",),
                notes="manual candidate",
                provenance_ref="user-entry:test",
            )

            self.assertTrue(result.created)
            self.assertEqual(result.record.metadata_status, "unknown")
            self.assertEqual(result.record.snapshot_status, "unknown")
            self.assertEqual(result.record.tags, ("orchestration", "evidence"))

            observations = ledger.rows("observations")
            kinds = [row["kind"] for row in observations]
            self.assertEqual(kinds, ["repo.record", "repo.ingested", "detective.triage"])

            detective = json.loads(observations[2]["payload_json"])
            self.assertFalse(detective["rejection_authority"])
            self.assertTrue(detective["requires_deeper_evidence"])
            self.assertIn("repository_metadata", detective["unknown"])
            self.assertIn("license_evidence", detective["unknown"])

            provenance = ledger.rows("provenance")
            self.assertEqual(len(provenance), 3)
            self.assertEqual(provenance[0]["source_ref"], "user-entry:test")

    def test_duplicate_canonical_identity_does_not_duplicate_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = EvidenceLedger(Path(tmp) / "ledger.db")
            ledger.initialize()
            ingestor = ManualRepositoryIngestor(ledger, dry_mode=True)

            first = ingestor.ingest("https://github.com/AlkaiDynamics/Archotraz")
            second = ingestor.ingest("https://www.github.com/alkaidynamics/archotraz.git")

            self.assertTrue(first.created)
            self.assertFalse(second.created)
            self.assertEqual(first.record.record_id, second.record.record_id)
            self.assertEqual(len(ledger.rows("observations")), 3)
            self.assertEqual(len(ledger.rows("provenance")), 3)


if __name__ == "__main__":
    unittest.main()
