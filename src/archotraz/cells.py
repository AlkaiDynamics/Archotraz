from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from typing import Any

from .evidence import EvidenceLedger


class CellHousingError(ValueError):
    pass


class CellBlock(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    GEN_POP = "GEN-POP"
    AD_SEG = "AD-SEG"

    @classmethod
    def coerce(cls, value: CellBlock | str) -> CellBlock:
        if isinstance(value, cls):
            return value
        try:
            return cls(str(value).strip().upper())
        except ValueError as exc:
            allowed = ", ".join(block.value for block in cls)
            raise CellHousingError(f"invalid cell block {value!r}; expected one of: {allowed}") from exc


@dataclass(frozen=True, slots=True)
class CellPlacement:
    repo_record_id: str
    block: CellBlock
    cell_id: str
    stage: str
    eligibility: str
    version: int
    rationale: str
    evidence_basis: tuple[str, ...]
    decision_id: str


class CellHousing:
    """Evidence-backed cell placement state.

    Cell Housing records explicit placement decisions. It does not score,
    classify, inspect source, or reject repositories.
    """

    def __init__(self, ledger: EvidenceLedger):
        self.ledger = ledger

    def place(
        self,
        repo_record_id: str,
        *,
        block: CellBlock | str,
        cell_id: str,
        rationale: str,
    ) -> CellPlacement:
        repo_evidence_id = self._require_repo_record(repo_record_id)
        if self.current(repo_record_id) is not None:
            raise CellHousingError(
                f"repository already has a cell placement: {repo_record_id}; use move() for a new version"
            )
        normalized_block = CellBlock.coerce(block)
        return self._record_placement(
            repo_record_id=repo_record_id,
            repo_evidence_id=repo_evidence_id,
            block=normalized_block,
            cell_id=self._require_text(cell_id, "cell_id"),
            rationale=self._require_text(rationale, "rationale"),
            version=1,
            kind="cell.placement",
            previous=None,
        )

    def move(
        self,
        repo_record_id: str,
        *,
        block: CellBlock | str,
        cell_id: str,
        rationale: str,
    ) -> CellPlacement:
        repo_evidence_id = self._require_repo_record(repo_record_id)
        previous = self.current(repo_record_id)
        if previous is None:
            raise CellHousingError(
                f"repository has no existing cell placement: {repo_record_id}; use place() first"
            )
        normalized_block = CellBlock.coerce(block)
        return self._record_placement(
            repo_record_id=repo_record_id,
            repo_evidence_id=repo_evidence_id,
            block=normalized_block,
            cell_id=self._require_text(cell_id, "cell_id"),
            rationale=self._require_text(rationale, "rationale"),
            version=previous.version + 1,
            kind="cell.movement",
            previous=previous,
        )

    def current(self, repo_record_id: str) -> CellPlacement | None:
        self._require_repo_record(repo_record_id)
        history = self._history_rows(repo_record_id)
        return history[-1] if history else None

    def history(self, repo_record_id: str) -> list[CellPlacement]:
        self._require_repo_record(repo_record_id)
        return self._history_rows(repo_record_id)

    def _record_placement(
        self,
        *,
        repo_record_id: str,
        repo_evidence_id: str,
        block: CellBlock,
        cell_id: str,
        rationale: str,
        version: int,
        kind: str,
        previous: CellPlacement | None,
    ) -> CellPlacement:
        evidence_basis = [repo_evidence_id]
        if previous is not None:
            evidence_basis.append(previous.decision_id)

        payload: dict[str, Any] = {
            "repo_record_id": repo_record_id,
            "block": block.value,
            "cell_id": cell_id,
            "stage": "cell_housing",
            "eligibility": "eligible",
            "version": version,
            "evidence_basis": evidence_basis,
        }
        decision = self.ledger.record_decision(
            kind,
            status="recorded",
            rationale=rationale,
            payload=payload,
        )
        self.ledger.record_provenance(
            decision,
            source_type="repo_record",
            source_ref=repo_evidence_id,
            metadata={
                "repo_record_id": repo_record_id,
                "block": block.value,
                "version": version,
            },
        )
        return CellPlacement(
            repo_record_id=repo_record_id,
            block=block,
            cell_id=cell_id,
            stage="cell_housing",
            eligibility="eligible",
            version=version,
            rationale=rationale,
            evidence_basis=tuple(evidence_basis),
            decision_id=decision.evidence_id,
        )

    def _require_repo_record(self, repo_record_id: str) -> str:
        candidate = repo_record_id.strip()
        if not candidate:
            raise CellHousingError("repo_record_id is required")
        for row in self.ledger.rows("observations"):
            if row["kind"] == "repo.record" and row["external_ref"] == candidate:
                return str(row["id"])
        raise CellHousingError(f"repo record not found: {candidate}")

    def _history_rows(self, repo_record_id: str) -> list[CellPlacement]:
        placements: list[CellPlacement] = []
        for row in self.ledger.rows("decisions"):
            if row["kind"] not in {"cell.placement", "cell.movement"}:
                continue
            payload = json.loads(row["payload_json"])
            if payload.get("repo_record_id") != repo_record_id:
                continue
            placements.append(
                CellPlacement(
                    repo_record_id=repo_record_id,
                    block=CellBlock.coerce(str(payload["block"])),
                    cell_id=str(payload["cell_id"]),
                    stage=str(payload["stage"]),
                    eligibility=str(payload["eligibility"]),
                    version=int(payload["version"]),
                    rationale=str(row["rationale"] or ""),
                    evidence_basis=tuple(str(value) for value in payload["evidence_basis"]),
                    decision_id=str(row["id"]),
                )
            )
        return sorted(placements, key=lambda placement: placement.version)

    @staticmethod
    def _require_text(value: str, name: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise CellHousingError(f"{name} is required")
        return normalized
