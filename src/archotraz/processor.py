from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from .evidence import EvidenceLedger
from .repos import RepoRegistry


_PROFILE_FIELDS = (
    "default_branch",
    "language",
    "license_spdx",
    "archived",
    "fork",
    "size_kb",
    "topics",
)


@dataclass(frozen=True, slots=True)
class RepoProfile:
    repo_id: str
    canonical_url: str
    default_branch: str | None
    language: str | None
    license_spdx: str | None
    archived: bool | None
    fork: bool | None
    size_kb: int | None
    topics: tuple[str, ...] | None
    detective_observation_id: str | None
    missing_fields: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "repo_id": self.repo_id,
            "canonical_url": self.canonical_url,
            "default_branch": self.default_branch,
            "language": self.language,
            "license_spdx": self.license_spdx,
            "archived": self.archived,
            "fork": self.fork,
            "size_kb": self.size_kb,
            "topics": None if self.topics is None else list(self.topics),
            "detective_observation_id": self.detective_observation_id,
            "missing_fields": list(self.missing_fields),
        }


@dataclass(slots=True)
class Processor:
    """Build deterministic, evidence-backed state without reopening repository source."""

    ledger: EvidenceLedger
    registry: RepoRegistry

    def profile(self, repo_id: str) -> RepoProfile:
        record = self.registry.get(repo_id)

        with self.ledger._connection() as conn:
            row = conn.execute(
                """
                SELECT id, payload_json
                  FROM observations
                 WHERE kind = 'detective.repo_metadata'
                   AND external_ref = ?
                 ORDER BY observed_at DESC, rowid DESC
                 LIMIT 1
                """,
                (repo_id,),
            ).fetchone()

        if row is None:
            payload: dict[str, Any] = {}
            observation_id = None
        else:
            payload = json.loads(str(row["payload_json"]))
            observation_id = str(row["id"])

        values: dict[str, Any] = {}
        missing: list[str] = []
        for field in _PROFILE_FIELDS:
            value = payload.get(field)
            if value is None:
                missing.append(field)
            values[field] = value

        raw_topics = values["topics"]
        topics = None if raw_topics is None else tuple(str(topic) for topic in raw_topics)

        return RepoProfile(
            repo_id=record.repo_id,
            canonical_url=record.canonical_url,
            default_branch=None if values["default_branch"] is None else str(values["default_branch"]),
            language=None if values["language"] is None else str(values["language"]),
            license_spdx=None if values["license_spdx"] is None else str(values["license_spdx"]),
            archived=None if values["archived"] is None else bool(values["archived"]),
            fork=None if values["fork"] is None else bool(values["fork"]),
            size_kb=None if values["size_kb"] is None else int(values["size_kb"]),
            topics=topics,
            detective_observation_id=observation_id,
            missing_fields=tuple(missing),
        )
