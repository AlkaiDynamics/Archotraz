from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

from .evidence import EvidenceLedger, _json, utc_now


_GITHUB_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")


class RepoInputError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RepoIdentity:
    provider: str
    owner: str
    name: str
    canonical_url: str
    identity_key: str


@dataclass(frozen=True, slots=True)
class RepoRecord:
    repo_id: str
    provider: str
    owner: str
    name: str
    source_url: str
    canonical_url: str
    identity_key: str
    priority: int | None
    tags: tuple[str, ...]
    notes: str | None
    status: str
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["tags"] = list(self.tags)
        return payload


@dataclass(frozen=True, slots=True)
class RepoIngestResult:
    record: RepoRecord
    created: bool


def canonicalize_repo_url(raw_url: str) -> RepoIdentity:
    raw = raw_url.strip()
    if not raw:
        raise RepoInputError("repository URL is required")

    parsed = urlsplit(raw)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise RepoInputError("repository URL must use http or https")
    if parsed.username is not None or parsed.password is not None:
        raise RepoInputError("repository URL must not embed credentials")

    host = (parsed.hostname or "").lower()
    if host == "www.github.com":
        host = "github.com"
    if host != "github.com":
        raise RepoInputError("MVP manual ingestion currently accepts github.com repository URLs only")

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 2:
        raise RepoInputError("repository URL must identify exactly one GitHub owner/repository")

    owner, name = parts
    if name.endswith(".git"):
        name = name[:-4]
    if not owner or not name or not _GITHUB_NAME.fullmatch(owner) or not _GITHUB_NAME.fullmatch(name):
        raise RepoInputError("repository owner/name contains unsupported characters")

    canonical_url = f"https://github.com/{owner}/{name}"
    identity_key = f"github:{owner.casefold()}/{name.casefold()}"
    return RepoIdentity("github", owner, name, canonical_url, identity_key)


class RepoRegistry:
    """Manual repository intake backed by the canonical SQLite state/evidence ledger."""

    def __init__(self, ledger: EvidenceLedger):
        self.ledger = ledger

    def add_manual(
        self,
        source_url: str,
        *,
        priority: int | None = None,
        tags: tuple[str, ...] = (),
        notes: str | None = None,
    ) -> RepoIngestResult:
        identity = canonicalize_repo_url(source_url)
        normalized_tags = tuple(dict.fromkeys(tag.strip() for tag in tags if tag.strip()))
        now = utc_now()

        with self.ledger._connection() as conn:
            existing = conn.execute(
                "SELECT * FROM repo_records WHERE identity_key = ?",
                (identity.identity_key,),
            ).fetchone()
            if existing is not None:
                record = self._row_to_record(existing)
                observation_id = uuid4().hex
                conn.execute(
                    """
                    INSERT INTO observations(id, kind, observed_at, source, external_ref, payload_json, interpretation_status)
                    VALUES(?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        observation_id,
                        "repo.ingest.duplicate",
                        now,
                        "manual",
                        record.repo_id,
                        _json({"repo_id": record.repo_id, "identity_key": record.identity_key}),
                        "raw",
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO provenance(id, evidence_type, evidence_id, source_type, source_ref, captured_at, metadata_json)
                    VALUES(?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        uuid4().hex,
                        "observation",
                        observation_id,
                        "manual_input",
                        source_url,
                        now,
                        _json({"canonical_url": record.canonical_url}),
                    ),
                )
                return RepoIngestResult(record, False)

            repo_id = uuid4().hex
            conn.execute(
                """
                INSERT INTO repo_records(
                    id, provider, owner, name, source_url, canonical_url, identity_key,
                    priority, tags_json, notes, status, created_at, updated_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    repo_id,
                    identity.provider,
                    identity.owner,
                    identity.name,
                    source_url,
                    identity.canonical_url,
                    identity.identity_key,
                    priority,
                    _json(list(normalized_tags)),
                    notes,
                    "recorded",
                    now,
                    now,
                ),
            )

            payload = {
                "repo_id": repo_id,
                "provider": identity.provider,
                "owner": identity.owner,
                "name": identity.name,
                "canonical_url": identity.canonical_url,
                "identity_key": identity.identity_key,
                "priority": priority,
                "tags": list(normalized_tags),
                "notes": notes,
            }
            observation_id = uuid4().hex
            conn.execute(
                """
                INSERT INTO observations(id, kind, observed_at, source, external_ref, payload_json, interpretation_status)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    observation_id,
                    "repo.ingested",
                    now,
                    "manual",
                    repo_id,
                    _json(payload),
                    "raw",
                ),
            )
            conn.execute(
                """
                INSERT INTO provenance(id, evidence_type, evidence_id, source_type, source_ref, captured_at, metadata_json)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid4().hex,
                    "observation",
                    observation_id,
                    "manual_input",
                    source_url,
                    now,
                    _json({"canonical_url": identity.canonical_url}),
                ),
            )

            row = conn.execute("SELECT * FROM repo_records WHERE id = ?", (repo_id,)).fetchone()
            assert row is not None
            return RepoIngestResult(self._row_to_record(row), True)

    def get(self, repo_id: str) -> RepoRecord:
        with self.ledger._connection() as conn:
            row = conn.execute("SELECT * FROM repo_records WHERE id = ?", (repo_id,)).fetchone()
        if row is None:
            raise KeyError(f"repo record not found: {repo_id}")
        return self._row_to_record(row)

    def list(self) -> list[RepoRecord]:
        with self.ledger._connection() as conn:
            rows = conn.execute("SELECT * FROM repo_records ORDER BY created_at, id").fetchall()
        return [self._row_to_record(row) for row in rows]

    @staticmethod
    def _row_to_record(row: Any) -> RepoRecord:
        return RepoRecord(
            repo_id=str(row["id"]),
            provider=str(row["provider"]),
            owner=str(row["owner"]),
            name=str(row["name"]),
            source_url=str(row["source_url"]),
            canonical_url=str(row["canonical_url"]),
            identity_key=str(row["identity_key"]),
            priority=None if row["priority"] is None else int(row["priority"]),
            tags=tuple(json.loads(str(row["tags_json"]))),
            notes=None if row["notes"] is None else str(row["notes"]),
            status=str(row["status"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )
