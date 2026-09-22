from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from itertools import combinations
from typing import Any

from .cells import CellHousing
from .repos import RepoRegistry


class GuardStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class GuardContract:
    name: str
    consumes: tuple[str, ...]
    produces: tuple[str, ...]
    objective: str
    constraints: tuple[str, ...]
    confidence: str
    cost: str
    deterministic: bool
    escalation_trigger: str
    declared_overlap: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "consumes": list(self.consumes),
            "produces": list(self.produces),
            "objective": self.objective,
            "constraints": list(self.constraints),
            "confidence": self.confidence,
            "cost": self.cost,
            "deterministic": self.deterministic,
            "escalation_trigger": self.escalation_trigger,
            "declared_overlap": list(self.declared_overlap),
        }


@dataclass(frozen=True, slots=True)
class PairCandidate:
    repo_a_id: str
    repo_b_id: str

    def __post_init__(self) -> None:
        if self.repo_b_id < self.repo_a_id:
            left = self.repo_b_id
            right = self.repo_a_id
            object.__setattr__(self, "repo_a_id", left)
            object.__setattr__(self, "repo_b_id", right)

    @property
    def pair_id(self) -> str:
        return f"{self.repo_a_id}::{self.repo_b_id}"

    def to_dict(self) -> dict[str, str]:
        return {
            "pair_id": self.pair_id,
            "repo_a_id": self.repo_a_id,
            "repo_b_id": self.repo_b_id,
        }


@dataclass(slots=True)
class PairUniverse:
    registry: RepoRegistry

    def enumerate(self) -> list[PairCandidate]:
        repo_ids = sorted(record.repo_id for record in self.registry.list())
        return [PairCandidate(left, right) for left, right in combinations(repo_ids, 2)]


@dataclass(frozen=True, slots=True)
class GuardResult:
    guard_name: str
    status: GuardStatus
    subject_ids: tuple[str, ...]
    evidence_used: tuple[str, ...]
    missing: tuple[str, ...]
    findings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "guard_name": self.guard_name,
            "status": self.status.value,
            "subject_ids": list(self.subject_ids),
            "evidence_used": list(self.evidence_used),
            "missing": list(self.missing),
            "findings": list(self.findings),
        }


@dataclass(slots=True)
class PairEligibilityGuard:
    """Cheap structural gate before deeper pair matching.

    PASS means only that the pair is distinct and both candidates have explicit Cell
    state. It makes no claim about compatibility, complementarity, or technical value.
    """

    registry: RepoRegistry
    housing: CellHousing

    contract = GuardContract(
        name="pair.cell-readiness",
        consumes=("RepoRecord", "CellAssignment"),
        produces=("GuardResult",),
        objective="Gate pair candidates on distinct identity and explicit Cell state before deeper matching.",
        constraints=(
            "pair members must be distinct",
            "both repositories must have an active Cell assignment",
        ),
        confidence="deterministic",
        cost="O(1)",
        deterministic=True,
        escalation_trigger="UNKNOWN when either Cell assignment is missing",
        declared_overlap=("Validator",),
    )

    def evaluate_ids(self, repo_a_id: str, repo_b_id: str) -> GuardResult:
        self.registry.get(repo_a_id)
        self.registry.get(repo_b_id)
        return self.evaluate(PairCandidate(repo_a_id, repo_b_id))

    def evaluate(self, pair: PairCandidate) -> GuardResult:
        if pair.repo_a_id == pair.repo_b_id:
            return GuardResult(
                guard_name=self.contract.name,
                status=GuardStatus.FAIL,
                subject_ids=(pair.repo_a_id, pair.repo_b_id),
                evidence_used=(),
                missing=(),
                findings=("Pair members must be distinct candidates.",),
            )

        assignments = (
            self.housing.current(pair.repo_a_id),
            self.housing.current(pair.repo_b_id),
        )
        repo_ids = (pair.repo_a_id, pair.repo_b_id)

        missing = tuple(
            f"cell_assignment:{repo_id}"
            for repo_id, assignment in zip(repo_ids, assignments, strict=True)
            if assignment is None
        )
        evidence_used = tuple(
            f"cell_assignment:{assignment.assignment_id}"
            for assignment in assignments
            if assignment is not None
        )

        if missing:
            return GuardResult(
                guard_name=self.contract.name,
                status=GuardStatus.UNKNOWN,
                subject_ids=repo_ids,
                evidence_used=evidence_used,
                missing=missing,
                findings=(
                    "Pair eligibility is unresolved because explicit Cell state is missing.",
                ),
            )

        return GuardResult(
            guard_name=self.contract.name,
            status=GuardStatus.PASS,
            subject_ids=repo_ids,
            evidence_used=evidence_used,
            missing=(),
            findings=(
                "Pair is structurally eligible for deeper matching; no compatibility or value claim is made.",
            ),
        )
