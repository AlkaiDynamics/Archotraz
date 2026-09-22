from __future__ import annotations

from dataclasses import asdict, dataclass
from itertools import combinations
from typing import Iterable

from .cells import CellHousing, CellHousingError, CellPlacement
from .evidence import EvidenceLedger, EvidenceRef


GUARD_ATTEMPT_KIND = "guard.matcher.exhaustive_pair_enumeration"


class GuardRunError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class GuardContract:
    name: str
    family: str
    algorithm: str
    consumes: tuple[str, ...]
    produces: tuple[str, ...]
    objective: str
    constraints: tuple[str, ...]
    evidence_used: tuple[str, ...]
    uncertainty: str
    cost: str
    deterministic: bool
    seed_required: bool
    escalation_trigger: str
    declared_overlap: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PairCandidate:
    left_repo_id: str
    right_repo_id: str
    left_placement_decision_id: str
    right_placement_decision_id: str
    left_block: str
    right_block: str
    left_cell_id: str
    right_cell_id: str
    attempt_id: str


@dataclass(frozen=True, slots=True)
class PairEnumerationResult:
    contract: GuardContract
    candidate_count: int
    pair_count: int
    complete_unordered_universe: bool
    attempt_id: str
    pairs: tuple[PairCandidate, ...]


class PairEnumerationGuard:
    """Matcher-family baseline that enumerates a complete unordered pair universe.

    Pair presence means only that both repositories were explicitly supplied to the
    candidate universe and had explicit current Cell Housing placements. It conveys
    no compatibility, quality, ranking, recommendation, or construction authority.
    """

    contract = GuardContract(
        name="matcher.exhaustive_pair_enumeration",
        family="matcher",
        algorithm="exhaustive_unordered_pair_enumeration",
        consumes=("explicit RepoRecord ids", "current CellPlacement"),
        produces=("complete unordered pair proposals",),
        objective="enumerate the complete unordered pair search universe",
        constraints=(
            "no scoring",
            "no ranking",
            "no repository rejection",
            "no automatic cell placement",
            "no source inspection",
            "no metadata fetch",
            "no Processor feature computation",
            "no Kitchen promotion",
        ),
        evidence_used=("repo.record observation", "current CellPlacement decision"),
        uncertainty="pair quality remains unknown",
        cost="O(n^2) pair enumeration after current-state lookup",
        deterministic=True,
        seed_required=False,
        escalation_trigger="pair evaluation requires grounded Processor/validation evidence",
        declared_overlap=("Matcher exhaustive unordered pair baseline",),
    )

    def __init__(self, ledger: EvidenceLedger):
        self.ledger = ledger
        self.housing = CellHousing(ledger)

    def run(self, repo_record_ids: Iterable[str]) -> PairEnumerationResult:
        raw_candidates = [str(value).strip() for value in repo_record_ids]
        attempt_id = self.ledger.begin_attempt(
            GUARD_ATTEMPT_KIND,
            {"candidate_repo_record_ids": raw_candidates},
        )
        try:
            candidates = sorted({candidate for candidate in raw_candidates if candidate})
            if len(candidates) < 2:
                raise GuardRunError("exhaustive pair enumeration requires at least two distinct candidates")

            placements: dict[str, CellPlacement] = {}
            for repo_id in candidates:
                try:
                    placement = self.housing.current(repo_id)
                except CellHousingError as exc:
                    raise GuardRunError(str(exc)) from exc
                if placement is None:
                    raise GuardRunError(f"repository has no explicit current CellPlacement: {repo_id}")
                placements[repo_id] = placement

            pairs = tuple(
                self._pair(left, right, placements[left], placements[right], attempt_id)
                for left, right in combinations(candidates, 2)
            )
            expected_count = len(candidates) * (len(candidates) - 1) // 2
            if len(pairs) != expected_count:
                raise GuardRunError(
                    f"incomplete unordered pair universe: expected {expected_count}, produced {len(pairs)}"
                )

            result = PairEnumerationResult(
                contract=self.contract,
                candidate_count=len(candidates),
                pair_count=len(pairs),
                complete_unordered_universe=True,
                attempt_id=attempt_id,
                pairs=pairs,
            )
            self.ledger.finish_attempt(
                attempt_id,
                status="succeeded",
                output=self._result_payload(result),
            )
            attempt_ref = EvidenceRef("attempt", attempt_id)
            for repo_id in candidates:
                placement = placements[repo_id]
                self.ledger.record_provenance(
                    attempt_ref,
                    source_type="cell_placement",
                    source_ref=placement.decision_id,
                    metadata={
                        "repo_record_id": repo_id,
                        "block": placement.block.value,
                        "cell_id": placement.cell_id,
                        "placement_version": placement.version,
                    },
                )
            return result
        except Exception as exc:
            error = exc if isinstance(exc, GuardRunError) else GuardRunError(str(exc))
            self.ledger.finish_attempt(attempt_id, status="failed", error_text=str(error))
            self.ledger.record_failure(
                GUARD_ATTEMPT_KIND,
                str(error),
                attempt_id=attempt_id,
                payload={"candidate_repo_record_ids": raw_candidates},
            )
            raise error from None

    @staticmethod
    def _pair(
        left_repo_id: str,
        right_repo_id: str,
        left: CellPlacement,
        right: CellPlacement,
        attempt_id: str,
    ) -> PairCandidate:
        return PairCandidate(
            left_repo_id=left_repo_id,
            right_repo_id=right_repo_id,
            left_placement_decision_id=left.decision_id,
            right_placement_decision_id=right.decision_id,
            left_block=left.block.value,
            right_block=right.block.value,
            left_cell_id=left.cell_id,
            right_cell_id=right.cell_id,
            attempt_id=attempt_id,
        )

    @staticmethod
    def _result_payload(result: PairEnumerationResult) -> dict[str, object]:
        return {
            "guard": result.contract.name,
            "candidate_count": result.candidate_count,
            "pair_count": result.pair_count,
            "complete_unordered_universe": result.complete_unordered_universe,
            "attempt_id": result.attempt_id,
            "pairs": [asdict(pair) for pair in result.pairs],
        }
