from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from archotraz.evidence import EvidenceLedger
from archotraz.repos import RepoInputError, RepoRegistry, canonicalize_repo_url


class RepoRegistryTests(unittest.TestCase):
    def make_registry(self, root: str) -> tuple[RepoRegistry, EvidenceLedger]:
        ledger = EvidenceLedger(Path(root) / "ledger.db")
        ledger.initialize()
        return RepoRegistry(ledger), ledger

    def test_canonicalize_github_repo_url(self) -> None:
        identity = canonicalize_repo_url("https://www.github.com/AlkaiDynamics/Archotraz.git?utm_source=test")
        self.assertEqual(identity.provider, "github")
        self.assertEqual(identity.owner, "AlkaiDynamics")
        self.assertEqual(identity.name, "Archotraz")
        self.assertEqual(identity.canonical_url, "https://github.com/AlkaiDynamics/Archotraz")
        self.assertEqual(identity.identity_key, "github:alkaidynamics/archotraz")

    def test_rejects_non_repository_or_non_github_url(self) -> None:
        with self.assertRaises(RepoInputError):
            canonicalize_repo_url("https://github.com/AlkaiDynamics/Archotraz/issues")
        with self.assertRaises(RepoInputError):
            canonicalize_repo_url("https://example.com/owner/repo")

    def test_rejects_non_http_urls_and_embedded_credentials(self) -> None:
        with self.assertRaises(RepoInputError):
            canonicalize_repo_url("ftp://github.com/AlkaiDynamics/Archotraz")
        with self.assertRaises(RepoInputError):
            canonicalize_repo_url("https://user:secret@github.com/AlkaiDynamics/Archotraz")

    def test_manual_ingest_is_idempotent_and_records_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry, ledger = self.make_registry(tmp)
            first = registry.add_manual(
                "https://github.com/AlkaiDynamics/Archotraz?utm_source=test",
                priority=7,
                tags=("core", "core", "manual"),
                notes="first intake",
            )
            second = registry.add_manual("https://github.com/alkaidynamics/archotraz.git")

            self.assertTrue(first.created)
            self.assertFalse(second.created)
            self.assertEqual(first.record.repo_id, second.record.repo_id)
            self.assertEqual(first.record.tags, ("core", "manual"))
            self.assertEqual(len(ledger.rows("repo_records")), 1)

            kinds = [row["kind"] for row in ledger.rows("observations")]
            self.assertIn("repo.ingested", kinds)
            self.assertIn("repo.ingest.duplicate", kinds)
            self.assertEqual(len(ledger.rows("provenance")), 2)

    def test_repo_record_does_not_hold_database_handle_open(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.db"
            ledger = EvidenceLedger(path)
            ledger.initialize()
            RepoRegistry(ledger).add_manual("https://github.com/AlkaiDynamics/Archotraz")
            path.unlink()
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
