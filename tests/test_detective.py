from __future__ import annotations

import json
import tempfile
import unittest
from unittest.mock import patch
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


class FakeHttpResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._raw = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> "FakeHttpResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return self._raw


class GitHubPublicMetadataSourceTests(unittest.TestCase):
    def test_timeout_must_be_positive(self) -> None:
        with self.assertRaises(ValueError):
            GitHubPublicMetadataSource(timeout_seconds=0)

    def test_maps_public_github_metadata_to_raw_observation(self) -> None:
        record = RepoRecord(
            repo_id="repo-1",
            provider="github",
            owner="AlkaiDynamics",
            name="Archotraz",
            source_url="https://github.com/AlkaiDynamics/Archotraz",
            canonical_url="https://github.com/AlkaiDynamics/Archotraz",
            identity_key="github:alkaidynamics/archotraz",
            priority=None,
            tags=(),
            notes=None,
            status="recorded",
            created_at="now",
            updated_at="now",
        )
        response = FakeHttpResponse(
            {
                "id": 123,
                "full_name": "AlkaiDynamics/Archotraz",
                "private": False,
                "fork": False,
                "archived": False,
                "disabled": False,
                "default_branch": "main",
                "language": "Python",
                "size": 42,
                "stargazers_count": 3,
                "forks_count": 1,
                "open_issues_count": 2,
                "license": {"spdx_id": "MIT"},
                "topics": ["repo-analysis"],
                "created_at": "created",
                "updated_at": "updated",
                "pushed_at": "pushed",
                "html_url": "https://github.com/AlkaiDynamics/Archotraz",
            }
        )

        captured: dict[str, object] = {}

        def fake_urlopen(req, timeout):
            captured["url"] = req.full_url
            captured["headers"] = {key.lower(): value for key, value in req.header_items()}
            captured["timeout"] = timeout
            return response

        with patch("archotraz.detective.request.urlopen", side_effect=fake_urlopen):
            observation = GitHubPublicMetadataSource(timeout_seconds=4.5).inspect(record)

        self.assertEqual(captured["url"], "https://api.github.com/repos/AlkaiDynamics/Archotraz")
        self.assertEqual(captured["timeout"], 4.5)
        self.assertIn("user-agent", captured["headers"])
        self.assertEqual(observation.source_type, "github_api")
        self.assertEqual(observation.source_ref, "https://api.github.com/repos/AlkaiDynamics/Archotraz")
        self.assertEqual(observation.payload["github_id"], 123)
        self.assertEqual(observation.payload["license_spdx"], "MIT")
        self.assertEqual(observation.payload["topics"], ["repo-analysis"])


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
