from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import uuid4

from .evidence import EvidenceLedger, _json, utc_now
from .repos import RepoRegistry


class CellBlock(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    GEN_POP = "GEN_POP"
    AD_SEG = "AD_SEG"


@dataclass(frozen=True, slots=True)
class CellAssignment:
    assignment_id: str
    repo_id: str
    block: CellBlock
    cell_label: str | None
    assignment_source: str
    policy_ref: str | None
    reason: str
    assigned_at: str
    superseded_at: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "assignment_id": self.assignment_id,
            "repo_id": self.repo_id,
            "block": self.block.value,
            "cell_label": self.cell_label,
            "assignment_source": self.assignment_source,
            "policy_ref": self.policy_ref,
            "reason": self.reason,
            "assigned_at": self.assigned_at,
            "superseded_at": self.superseded_at,
        }


@dataclass(slots=True)
class CellHousing:
    """Reversible cell state. It stores decisions; it does not infer them."""

    ledger: EvidenceLedger
    registry: RepoRegistry

    def assign(
        self,
        repo_id: str,
        block: CellBlock | str,
        *,
        source: str,
        reason: str,
        cell_label: str | None = None,
        policy_ref: str | None = None,
    ) -> CellAssignment:
        self.registry.get(repo_id)

        source = source.strip()
        reason = reason.strip()
        if not source:
            raise ValueError("assignment source is required")
        if not reason:
            raise ValueError("assignment reason is required")

        normalized_block = block if isinstance(block, CellBlock) else CellBlock(str(block))
        normalized_label = None if cell_label is None else cell_label.strip() or None
        normalized_policy_ref = None if policy_ref is None else policy_ref.strip() or None

        now = utc_now()
        assignment_id = uuid4().hex
        decision_id = uuid4().hex

        with self.ledger._connection() as conn:
            conn.execute(
                """
                UPDATE cell_assignments
                   SET superseded_at = ?
                 WHERE repo_id = ?
                   AND superseded_at IS NULL
                """,
                (now, repo_id),
            )
            conn.execute(
                """
                INSERT INTO cell_assignments(
                    id, repo_id, block, cell_label, assignment_source,
                    policy_ref, reason, assigned_at, superseded_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    assignment_id,
                    repo_id,
                    normalized_block.value,
                    normalized_label,
                    source,
                    normalized_policy_ref,
                    reason,
                    now,
                ),
            )
            decision_payload = {
                "assignment_id": assignment_id,
                "repo_id": repo_id,
                "block": normalized_block.value,
                "cell_label": normalized_label,
                "assignment_source": source,
                "policy_ref": normalized_policy_ref,
            }
            conn.execute(
                """
                INSERT INTO decisions(id, kind, decided_at, status, rationale, payload_json)
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                (
                    decision_id,
                    "cell.assignment",
                    now,
                    "applied",
                    reason,
                    _json(decision_payload),
                ),
            )
            conn.execute(
                """
                INSERT INTO provenance(
                    id, evidence_type, evidence_id, source_type,
                    source_ref, captured_at, metadata_json
                )
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid4().hex,
                    "decision",
                    decision_id,
                    source,
                    normalized_policy_ref or repo_id,
                    now,
                    _json({"repo_id": repo_id, "assignment_id": assignment_id}),
                ),
            )

        assignment = self.current(repo_id)
        assert assignment is not None
        return assignment

    def current(self, repo_id: str) -> CellAssignment | None:
        self.registry.get(repo_id)
        with self.ledger._connection() as conn:
            row = conn.execute(
                """
                SELECT *
                  FROM cell_assignments
                 WHERE repo_id = ?
                   AND superseded_at IS NULL
                 ORDER BY assigned_at DESC, rowid DESC
                 LIMIT 1
                """,
                (repo_id,),
            ).fetchone()
        return None if row is None else self._row_to_assignment(row)

    def history(self, repo_id: str) -> list[CellAssignment]:
        self.registry.get(repo_id)
        with self.ledger._connection() as conn:
            rows = conn.execute(
                """
                SELECT *
                  FROM cell_assignments
                 WHERE repo_id = ?
                 ORDER BY assigned_at, rowid
                """,
                (repo_id,),
            ).fetchall()
        return [self._row_to_assignment(row) for row in rows]

    @staticmethod
    def _row_to_assignment(row: Any) -> CellAssignment:
        return CellAssignment(
            assignment_id=str(row["id"]),
            repo_id=str(row["repo_id"]),
            block=CellBlock(str(row["block"])),
            cell_label=None if row["cell_label"] is None else str(row["cell_label"]),
            assignment_source=str(row["assignment_source"]),
            policy_ref=None if row["policy_ref"] is None else str(row["policy_ref"]),
            reason=str(row["reason"]),
            assigned_at=str(row["assigned_at"]),
            superseded_at=None if row["superseded_at"] is None else str(row["superseded_at"]),
        )
