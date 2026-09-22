from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from archotraz.detective import Detective, GitHubPublicMetadataSource, SourceObservation
from archotraz.evidence import EvidenceLedger
from archotraz.repos import RepoRecord, RepoRegistry


class FakeSource:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.seen: list[RepoRecord] = []

    def inspect(self, record: RepoRecord) -> SourceObservation:
        self.seen.append(record)
        if self.fail:
            raise RuntimeError("metadata unavailable")
        return SourceObservation(
            payload={
                "repo_id": record.repo_id,
                "provider": record.provider,
                "full_name": f"{record.owner}/{record.name}",
                "default_branch": "main",
                "language": "Python",
            },
            source_type="fixture",
            source_ref="fixture://repo-metadata",
        )


class GitHubPublicMetadataSourceTests(unittest.TestCase):
    def test_timeout_must_be_positive(self) -> None:
        with self.assertRaises(ValueError):
            GitHubPublicMetadataSource(timeout_seconds=0)


class DetectiveTests(unittest.TestCase):
    def make_subject(self, root: str, source: FakeSource) -> tuple[Detective, RepoRegistry, EvidenceLedger]:
        ledger = EvidenceLedger(Path(root) / "ledger.db")
        ledger.initialize()
        registry = RepoRegistry(ledger)
        return Detective(ledger=ledger, registry=registry, source=source), registry, ledger

    def test_triage_records_cheap_metadata_without_making_admission_decision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = FakeSource()
            detective, registry, ledger = self.make_subject(tmp, source)
            ingested = registry.add_manual("https://github.com/AlkaiDynamics/Archotraz")

            result = detective.triage(ingested.record.repo_id)

            self.assertEqual(result.payload["full_name"], "AlkaiDynamics/Archotraz")
            self.assertEqual(source.seen, [ingested.record])

            attempts = ledger.rows("attempts")
            self.assertEqual(len(attempts), 1)
            self.assertEqual(attempts[0]["kind"], "detective.triage")
            self.assertEqual(attempts[0]["status"], "succeeded")

            observations = ledger.rows("observations")
            self.assertEqual(
                [row["kind"] for row in observations],
                ["repo.ingested", "detective.repo_metadata"],
            )
            self.assertEqual(len(ledger.rows("decisions")), 0)

            provenance = ledger.rows("provenance")
            self.assertEqual(len(provenance), 2)
            self.assertEqual(provenance[-1]["source_type"], "fixture")
            self.assertEqual(provenance[-1]["source_ref"], "fixture://repo-metadata")

    def test_triage_failure_is_evidence_and_does_not_reject_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = FakeSource(fail=True)
            detective, registry, ledger = self.make_subject(tmp, source)
            ingested = registry.add_manual("https://github.com/AlkaiDynamics/Archotraz")

            with self.assertRaisesRegex(RuntimeError, "metadata unavailable"):
                detective.triage(ingested.record.repo_id)

            attempts = ledger.rows("attempts")
            self.assertEqual(attempts[0]["status"], "failed")
            self.assertEqual(ledger.rows("failures")[0]["kind"], "detective.triage")
            self.assertEqual(len(ledger.rows("decisions")), 0)
            self.assertEqual(registry.get(ingested.record.repo_id).status, "recorded")


if __name__ == "__main__":
    unittest.main()
