from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Any
from urllib.parse import urlparse

from .evidence import EvidenceLedger


class RepositoryInputError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RepoRecord:
    record_id: str
    provider: str
    owner: str
    name: str
    canonical_url: str
    submitted_url: str
    priority: str | None
    tags: tuple[str, ...]
    dry_mode: bool
    desired_block: str | None
    algorithm_overrides: tuple[str, ...]
    guard_overrides: tuple[str, ...]
    notes: str | None
    metadata_status: str = "unknown"
    snapshot_status: str = "unknown"

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class IngestResult:
    record: RepoRecord
    created: bool
    record_evidence_id: str
    ingested_evidence_id: str | None
    detective_evidence_id: str | None


def canonicalize_repository_url(url: str) -> tuple[str, str, str, str]:
    submitted = url.strip()
    if not submitted:
        raise RepositoryInputError("repository URL is required")

    parsed = urlparse(submitted)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise RepositoryInputError("repository URL must use http or https")

    host = parsed.netloc.casefold()
    if host == "www.github.com":
        host = "github.com"
    if host != "github.com":
        raise RepositoryInputError(f"unsupported repository provider: {parsed.netloc}")

    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) != 2:
        raise RepositoryInputError("GitHub repository URL must be https://github.com/<owner>/<repo>")

    owner = parts[0].strip()
    name = parts[1].strip()
    if name.casefold().endswith(".git"):
        name = name[:-4]

    if not owner or not name:
        raise RepositoryInputError("GitHub repository owner and name are required")

    identity_owner = owner.casefold()
    identity_name = name.casefold()
    canonical_url = f"https://github.com/{identity_owner}/{identity_name}"
    record_id = f"repo:github:{identity_owner}/{identity_name}"
    return record_id, identity_owner, identity_name, canonical_url


class Detective:
    """Cheapest repository examination stage.

    This first slice intentionally has no rejection authority. It records what is
    known from manual identity only and preserves all missing evidence as unknown.
    """

    def __init__(self, ledger: EvidenceLedger):
        self.ledger = ledger

    def triage(self, record: RepoRecord) -> str:
        payload = {
            "record_id": record.record_id,
            "canonical_url": record.canonical_url,
            "stage": "detective",
            "evidence_scope": "manual_identity_only",
            "observed": {
                "provider": record.provider,
                "owner": record.owner,
                "name": record.name,
                "tags": list(record.tags),
                "priority": record.priority,
                "desired_block": record.desired_block,
            },
            "unknown": [
                "repository_metadata",
                "readme",
                "package_metadata",
                "source_signals",
                "commit_identity",
                "license_evidence",
                "security_evidence",
                "capability_evidence",
            ],
            "rejection_authority": False,
            "requires_deeper_evidence": True,
        }
        evidence = self.ledger.record_observation(
            "detective.triage",
            "archotraz.detective",
            payload,
            external_ref=record.record_id,
            interpretation_status="derived_from_manual_identity",
        )
        self.ledger.record_provenance(
            evidence,
            source_type="repo_record",
            source_ref=record.record_id,
            metadata={"authority": "non_rejecting"},
        )
        return evidence.evidence_id


class ManualRepositoryIngestor:
    def __init__(self, ledger: EvidenceLedger, *, dry_mode: bool):
        self.ledger = ledger
        self.dry_mode = dry_mode
        self.detective = Detective(ledger)

    def ingest(
        self,
        url: str,
        *,
        priority: str | None = None,
        tags: tuple[str, ...] = (),
        desired_block: str | None = None,
        algorithm_overrides: tuple[str, ...] = (),
        guard_overrides: tuple[str, ...] = (),
        notes: str | None = None,
        provenance_ref: str | None = None,
    ) -> IngestResult:
        record_id, owner, name, canonical_url = canonicalize_repository_url(url)

        existing = self._find_existing(record_id)
        if existing is not None:
            return IngestResult(
                record=existing[0],
                created=False,
                record_evidence_id=existing[1],
                ingested_evidence_id=None,
                detective_evidence_id=None,
            )

        record = RepoRecord(
            record_id=record_id,
            provider="github",
            owner=owner,
            name=name,
            canonical_url=canonical_url,
            submitted_url=url.strip(),
            priority=priority,
            tags=tuple(dict.fromkeys(tag.strip() for tag in tags if tag.strip())),
            dry_mode=self.dry_mode,
            desired_block=desired_block,
            algorithm_overrides=tuple(
                dict.fromkeys(value.strip() for value in algorithm_overrides if value.strip())
            ),
            guard_overrides=tuple(
                dict.fromkeys(value.strip() for value in guard_overrides if value.strip())
            ),
            notes=notes,
        )

        source_ref = provenance_ref or record.submitted_url
        record_evidence = self.ledger.record_observation(
            "repo.record",
            "manual_input",
            record.to_payload(),
            external_ref=record.record_id,
            interpretation_status="structured_input",
        )
        self.ledger.record_provenance(
            record_evidence,
            source_type="manual_input",
            source_ref=source_ref,
            metadata={"submitted_url": record.submitted_url},
        )

        ingested_evidence = self.ledger.record_observation(
            "repo.ingested",
            "archotraz.ingest",
            {
                "record_id": record.record_id,
                "canonical_url": record.canonical_url,
                "record_evidence_id": record_evidence.evidence_id,
            },
            external_ref=record.record_id,
            interpretation_status="event",
        )
        self.ledger.record_provenance(
            ingested_evidence,
            source_type="observation",
            source_ref=record_evidence.evidence_id,
            metadata={"event": "RepoIngested"},
        )

        detective_evidence_id = self.detective.triage(record)
        return IngestResult(
            record=record,
            created=True,
            record_evidence_id=record_evidence.evidence_id,
            ingested_evidence_id=ingested_evidence.evidence_id,
            detective_evidence_id=detective_evidence_id,
        )

    def _find_existing(self, record_id: str) -> tuple[RepoRecord, str] | None:
        for row in self.ledger.rows("observations"):
            if row["kind"] != "repo.record" or row["external_ref"] != record_id:
                continue
            payload = json.loads(row["payload_json"])
            return (
                RepoRecord(
                    record_id=str(payload["record_id"]),
                    provider=str(payload["provider"]),
                    owner=str(payload["owner"]),
                    name=str(payload["name"]),
                    canonical_url=str(payload["canonical_url"]),
                    submitted_url=str(payload["submitted_url"]),
                    priority=payload.get("priority"),
                    tags=tuple(payload.get("tags", [])),
                    dry_mode=bool(payload["dry_mode"]),
                    desired_block=payload.get("desired_block"),
                    algorithm_overrides=tuple(payload.get("algorithm_overrides", [])),
                    guard_overrides=tuple(payload.get("guard_overrides", [])),
                    notes=payload.get("notes"),
                    metadata_status=str(payload.get("metadata_status", "unknown")),
                    snapshot_status=str(payload.get("snapshot_status", "unknown")),
                ),
                str(row["id"]),
            )
        return None
