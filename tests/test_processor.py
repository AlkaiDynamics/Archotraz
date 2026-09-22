from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from archotraz.evidence import EvidenceLedger
from archotraz.processor import Processor
from archotraz.repos import RepoRegistry


class ProcessorTests(unittest.TestCase):
    def make_subject(self, root: str) -> tuple[Processor, RepoRegistry, EvidenceLedger]:
        ledger = EvidenceLedger(Path(root) / "ledger.db")
        ledger.initialize()
        registry = RepoRegistry(ledger)
        return Processor(ledger=ledger, registry=registry), registry, ledger

    def test_profile_preserves_unknowns_when_detective_evidence_is_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            processor, registry, _ = self.make_subject(tmp)
            ingested = registry.add_manual("https://github.com/AlkaiDynamics/Archotraz")

            profile = processor.profile(ingested.record.repo_id)

            self.assertEqual(profile.repo_id, ingested.record.repo_id)
            self.assertEqual(profile.canonical_url, "https://github.com/AlkaiDynamics/Archotraz")
            self.assertIsNone(profile.language)
            self.assertIsNone(profile.license_spdx)
            self.assertIsNone(profile.archived)
            self.assertIsNone(profile.fork)
            self.assertIsNone(profile.size_kb)
            self.assertIsNone(profile.topics)
            self.assertIsNone(profile.detective_observation_id)
            self.assertEqual(
                set(profile.missing_fields),
                {
                    "default_branch",
                    "language",
                    "license_spdx",
                    "archived",
                    "fork",
                    "size_kb",
                    "topics",
                },
            )

    def test_profile_uses_latest_detective_observation_without_turning_zero_or_false_into_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            processor, registry, ledger = self.make_subject(tmp)
            ingested = registry.add_manual("https://github.com/AlkaiDynamics/Archotraz")
            repo_id = ingested.record.repo_id

            older = ledger.record_observation(
                "detective.repo_metadata",
                "fixture",
                {
                    "repo_id": repo_id,
                    "default_branch": "master",
                    "language": None,
                    "license_spdx": None,
                    "archived": None,
                    "fork": None,
                    "size_kb": None,
                    "topics": None,
                },
                external_ref=repo_id,
            )
            newer = ledger.record_observation(
                "detective.repo_metadata",
                "fixture",
                {
                    "repo_id": repo_id,
                    "default_branch": "main",
                    "language": "Python",
                    "license_spdx": "MIT",
                    "archived": False,
                    "fork": False,
                    "size_kb": 0,
                    "topics": [],
                },
                external_ref=repo_id,
            )

            profile = processor.profile(repo_id)

            self.assertNotEqual(older.evidence_id, newer.evidence_id)
            self.assertEqual(profile.detective_observation_id, newer.evidence_id)
            self.assertEqual(profile.default_branch, "main")
            self.assertEqual(profile.language, "Python")
            self.assertEqual(profile.license_spdx, "MIT")
            self.assertFalse(profile.archived)
            self.assertFalse(profile.fork)
            self.assertEqual(profile.size_kb, 0)
            self.assertEqual(profile.topics, ())
            self.assertEqual(profile.missing_fields, ())


if __name__ == "__main__":
    unittest.main()
