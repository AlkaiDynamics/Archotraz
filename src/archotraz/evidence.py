from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterable
from uuid import uuid4


SCHEMA_VERSION = 1
CANONICAL_TABLES = (
    "observations",
    "claims",
    "failures",
    "attempts",
    "decisions",
    "supersessions",
    "contradictions",
    "provenance",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


@dataclass(frozen=True, slots=True)
class EvidenceRef:
    evidence_type: str
    evidence_id: str


class EvidenceLedger:
    """Canonical Archotraz evidence/state ledger.

    SQLite is authoritative. External systems, caches, vectors, and runtime logs are
    sources of observations; they are not alternate truth stores.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS attempts (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    external_ref TEXT,
                    request_id TEXT,
                    input_json TEXT NOT NULL,
                    output_json TEXT,
                    error_text TEXT
                );

                CREATE TABLE IF NOT EXISTS observations (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    source TEXT NOT NULL,
                    external_ref TEXT,
                    payload_json TEXT NOT NULL,
                    interpretation_status TEXT NOT NULL DEFAULT 'raw'
                );

                CREATE TABLE IF NOT EXISTS claims (
                    id TEXT PRIMARY KEY,
                    statement TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    confidence REAL,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS failures (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    attempt_id TEXT,
                    error_text TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    FOREIGN KEY (attempt_id) REFERENCES attempts(id)
                );

                CREATE TABLE IF NOT EXISTS decisions (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    decided_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    rationale TEXT,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS supersessions (
                    id TEXT PRIMARY KEY,
                    superseded_type TEXT NOT NULL,
                    superseded_id TEXT NOT NULL,
                    superseding_type TEXT NOT NULL,
                    superseding_id TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    reason TEXT
                );

                CREATE TABLE IF NOT EXISTS contradictions (
                    id TEXT PRIMARY KEY,
                    left_type TEXT NOT NULL,
                    left_id TEXT NOT NULL,
                    right_type TEXT NOT NULL,
                    right_id TEXT NOT NULL,
                    detected_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    detail TEXT
                );

                CREATE TABLE IF NOT EXISTS provenance (
                    id TEXT PRIMARY KEY,
                    evidence_type TEXT NOT NULL,
                    evidence_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_ref TEXT NOT NULL,
                    captured_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_attempts_kind_started ON attempts(kind, started_at);
                CREATE INDEX IF NOT EXISTS idx_observations_kind_observed ON observations(kind, observed_at);
                CREATE INDEX IF NOT EXISTS idx_provenance_evidence ON provenance(evidence_type, evidence_id);
                """
            )
            conn.execute(
                "INSERT INTO schema_meta(key, value) VALUES('schema_version', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (str(SCHEMA_VERSION),),
            )

    def begin_attempt(self, kind: str, inputs: Any, *, request_id: str | None = None) -> str:
        attempt_id = uuid4().hex
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO attempts(id, kind, status, started_at, request_id, input_json) VALUES(?, ?, ?, ?, ?, ?)",
                (attempt_id, kind, "started", utc_now(), request_id, _json(inputs)),
            )
        return attempt_id

    def finish_attempt(
        self,
        attempt_id: str,
        *,
        status: str,
        output: Any | None = None,
        error_text: str | None = None,
        external_ref: str | None = None,
        request_id: str | None = None,
    ) -> None:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                UPDATE attempts
                   SET status = ?, finished_at = ?, external_ref = COALESCE(?, external_ref),
                       request_id = COALESCE(?, request_id), output_json = ?, error_text = ?
                 WHERE id = ?
                """,
                (status, utc_now(), external_ref, request_id, None if output is None else _json(output), error_text, attempt_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"attempt not found: {attempt_id}")

    def record_observation(
        self,
        kind: str,
        source: str,
        payload: Any,
        *,
        external_ref: str | None = None,
        interpretation_status: str = "raw",
    ) -> EvidenceRef:
        observation_id = uuid4().hex
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO observations(id, kind, observed_at, source, external_ref, payload_json, interpretation_status)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    observation_id,
                    kind,
                    utc_now(),
                    source,
                    external_ref,
                    _json(payload),
                    interpretation_status,
                ),
            )
        return EvidenceRef("observation", observation_id)

    def record_failure(self, kind: str, error_text: str, *, attempt_id: str | None = None, payload: Any = None) -> EvidenceRef:
        failure_id = uuid4().hex
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO failures(id, kind, occurred_at, attempt_id, error_text, payload_json) VALUES(?, ?, ?, ?, ?, ?)",
                (failure_id, kind, utc_now(), attempt_id, error_text, _json({} if payload is None else payload)),
            )
        return EvidenceRef("failure", failure_id)

    def record_provenance(
        self,
        evidence: EvidenceRef,
        *,
        source_type: str,
        source_ref: str,
        metadata: Any = None,
    ) -> str:
        provenance_id = uuid4().hex
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO provenance(id, evidence_type, evidence_id, source_type, source_ref, captured_at, metadata_json)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    provenance_id,
                    evidence.evidence_type,
                    evidence.evidence_id,
                    source_type,
                    source_ref,
                    utc_now(),
                    _json({} if metadata is None else metadata),
                ),
            )
        return provenance_id

    def table_names(self) -> set[str]:
        with self.connect() as conn:
            rows: Iterable[sqlite3.Row] = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            return {str(row["name"]) for row in rows}

    def rows(self, table: str) -> list[dict[str, Any]]:
        if table not in {*CANONICAL_TABLES, "schema_meta"}:
            raise ValueError(f"table is not queryable through this helper: {table}")
        with self.connect() as conn:
            return [dict(row) for row in conn.execute(f"SELECT * FROM {table} ORDER BY rowid")]
