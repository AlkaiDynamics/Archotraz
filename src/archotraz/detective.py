from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Protocol
from urllib import error, request

from .evidence import EvidenceLedger
from .repos import RepoRecord, RepoRegistry


class DetectiveSourceError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class SourceObservation:
    payload: dict[str, Any]
    source_type: str
    source_ref: str


class RepoMetadataSource(Protocol):
    def inspect(self, record: RepoRecord) -> SourceObservation: ...


@dataclass(slots=True)
class GitHubPublicMetadataSource:
    timeout_seconds: float = 10.0

    def inspect(self, record: RepoRecord) -> SourceObservation:
        if record.provider != "github":
            raise DetectiveSourceError(f"unsupported provider: {record.provider}")

        api_url = f"https://api.github.com/repos/{record.owner}/{record.name}"
        req = request.Request(
            api_url,
            headers={
                "accept": "application/vnd.github+json",
                "user-agent": "archotraz-detective/0.1",
            },
            method="GET",
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                raw = response.read()
        except error.HTTPError as exc:
            raise DetectiveSourceError(f"GitHub metadata returned HTTP {exc.code}") from exc
        except error.URLError as exc:
            raise DetectiveSourceError(f"GitHub metadata request failed: {exc.reason}") from exc

        decoded = json.loads(raw.decode("utf-8"))
        license_value = decoded.get("license")
        payload = {
            "repo_id": record.repo_id,
            "provider": "github",
            "github_id": decoded.get("id"),
            "full_name": decoded.get("full_name"),
            "private": decoded.get("private"),
            "fork": decoded.get("fork"),
            "archived": decoded.get("archived"),
            "disabled": decoded.get("disabled"),
            "default_branch": decoded.get("default_branch"),
            "language": decoded.get("language"),
            "size_kb": decoded.get("size"),
            "stargazers_count": decoded.get("stargazers_count"),
            "forks_count": decoded.get("forks_count"),
            "open_issues_count": decoded.get("open_issues_count"),
            "license_spdx": license_value.get("spdx_id") if isinstance(license_value, dict) else None,
            "topics": decoded.get("topics") or [],
            "created_at": decoded.get("created_at"),
            "updated_at": decoded.get("updated_at"),
            "pushed_at": decoded.get("pushed_at"),
            "html_url": decoded.get("html_url"),
        }
        return SourceObservation(payload=payload, source_type="github_api", source_ref=api_url)


@dataclass(slots=True)
class Detective:
    ledger: EvidenceLedger
    registry: RepoRegistry
    source: RepoMetadataSource

    def triage(self, repo_id: str) -> SourceObservation:
        record = self.registry.get(repo_id)
        attempt_id = self.ledger.begin_attempt(
            "detective.triage",
            {"repo_id": record.repo_id, "canonical_url": record.canonical_url},
        )
        try:
            observation = self.source.inspect(record)
        except Exception as exc:
            self.ledger.finish_attempt(
                attempt_id,
                status="failed",
                error_text=str(exc),
                external_ref=record.repo_id,
            )
            failure = self.ledger.record_failure(
                "detective.triage",
                str(exc),
                attempt_id=attempt_id,
                payload={"repo_id": record.repo_id, "canonical_url": record.canonical_url},
            )
            self.ledger.record_provenance(
                failure,
                source_type="repo_record",
                source_ref=record.repo_id,
                metadata={"canonical_url": record.canonical_url},
            )
            raise

        self.ledger.finish_attempt(
            attempt_id,
            status="succeeded",
            output=observation.payload,
            external_ref=record.repo_id,
        )
        evidence = self.ledger.record_observation(
            "detective.repo_metadata",
            observation.source_type,
            observation.payload,
            external_ref=record.repo_id,
        )
        self.ledger.record_provenance(
            evidence,
            source_type=observation.source_type,
            source_ref=observation.source_ref,
            metadata={
                "repo_id": record.repo_id,
                "canonical_url": record.canonical_url,
                "attempt_id": attempt_id,
            },
        )
        return observation
