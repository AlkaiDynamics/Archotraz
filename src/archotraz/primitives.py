from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from .evidence import EvidenceLedger, EvidenceRef
from .guards import PairCandidate
from .repos import RepoRegistry


_PRIMITIVE_FIELDS = (
    "mechanisms",
    "targets",
    "have",
    "need",
    "data_models",
    "access_patterns",
    "fidelity",
    "debt",
)


def _normalize_terms(values: tuple[str, ...] | None) -> tuple[str, ...] | None:
    if values is None:
        return None
    return tuple(sorted({value.strip().casefold() for value in values if value.strip()}))


@dataclass(frozen=True, slots=True)
class PrimitiveProfile:
    repo_id: str
    observation_id: str | None
    mechanisms: tuple[str, ...] | None
    targets: tuple[str, ...] | None
    have: tuple[str, ...] | None
    need: tuple[str, ...] | None
    data_models: tuple[str, ...] | None
    access_patterns: tuple[str, ...] | None
    fidelity: float | None
    debt: float | None
    missing_fields: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "repo_id": self.repo_id,
            "observation_id": self.observation_id,
            "mechanisms": None if self.mechanisms is None else list(self.mechanisms),
            "targets": None if self.targets is None else list(self.targets),
            "have": None if self.have is None else list(self.have),
            "need": None if self.need is None else list(self.need),
            "data_models": None if self.data_models is None else list(self.data_models),
            "access_patterns": None if self.access_patterns is None else list(self.access_patterns),
            "fidelity": self.fidelity,
            "debt": self.debt,
            "missing_fields": list(self.missing_fields),
        }


@dataclass(slots=True)
class PrimitiveEvidenceStore:
    """Record and retrieve raw repository primitives with explicit provenance.

    These observations are inputs to matching, not scores or admission decisions.
    """

    ledger: EvidenceLedger
    registry: RepoRegistry

    def record(
        self,
        repo_id: str,
        *,
        mechanisms: tuple[str, ...] | None = None,
        targets: tuple[str, ...] | None = None,
        have: tuple[str, ...] | None = None,
        need: tuple[str, ...] | None = None,
        data_models: tuple[str, ...] | None = None,
        access_patterns: tuple[str, ...] | None = None,
        fidelity: float | None = None,
        debt: float | None = None,
        source: str,
        source_ref: str,
    ) -> EvidenceRef:
        self.registry.get(repo_id)
        normalized_source = source.strip()
        normalized_source_ref = source_ref.strip()
        if not normalized_source:
            raise ValueError("primitive evidence source is required")
        if not normalized_source_ref:
            raise ValueError("primitive evidence source_ref is required")

        payload: dict[str, Any] = {"repo_id": repo_id}
        optional_terms = {
            "mechanisms": mechanisms,
            "targets": targets,
            "have": have,
            "need": need,
            "data_models": data_models,
            "access_patterns": access_patterns,
        }
        for field, values in optional_terms.items():
            normalized = _normalize_terms(values)
            if normalized is not None:
                payload[field] = list(normalized)
        if fidelity is not None:
            payload["fidelity"] = float(fidelity)
        if debt is not None:
            payload["debt"] = float(debt)

        if len(payload) == 1:
            raise ValueError("at least one primitive field must be observed")

        evidence = self.ledger.record_observation(
            "repo.primitives",
            normalized_source,
            payload,
            external_ref=repo_id,
        )
        self.ledger.record_provenance(
            evidence,
            source_type=normalized_source,
            source_ref=normalized_source_ref,
            metadata={"repo_id": repo_id, "fields": sorted(key for key in payload if key != "repo_id")},
        )
        return evidence

    def latest(self, repo_id: str) -> PrimitiveProfile:
        self.registry.get(repo_id)
        with self.ledger._connection() as conn:
            row = conn.execute(
                """
                SELECT id, payload_json
                  FROM observations
                 WHERE kind = 'repo.primitives'
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

        def terms(field: str) -> tuple[str, ...] | None:
            value = payload.get(field)
            return None if value is None else tuple(str(item) for item in value)

        missing = tuple(field for field in _PRIMITIVE_FIELDS if payload.get(field) is None)
        return PrimitiveProfile(
            repo_id=repo_id,
            observation_id=observation_id,
            mechanisms=terms("mechanisms"),
            targets=terms("targets"),
            have=terms("have"),
            need=terms("need"),
            data_models=terms("data_models"),
            access_patterns=terms("access_patterns"),
            fidelity=None if payload.get("fidelity") is None else float(payload["fidelity"]),
            debt=None if payload.get("debt") is None else float(payload["debt"]),
            missing_fields=missing,
        )


@dataclass(frozen=True, slots=True)
class RawPairFeatures:
    pair_id: str
    repo_a_id: str
    repo_b_id: str
    shared_mechanisms: tuple[str, ...]
    target_overlap: tuple[str, ...]
    a_need_b_have: tuple[str, ...]
    b_need_a_have: tuple[str, ...]
    data_model_overlap: tuple[str, ...]
    access_pattern_overlap: tuple[str, ...]
    missing: tuple[str, ...]
    evidence_used: tuple[str, ...]
    score: None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "pair_id": self.pair_id,
            "repo_a_id": self.repo_a_id,
            "repo_b_id": self.repo_b_id,
            "shared_mechanisms": list(self.shared_mechanisms),
            "target_overlap": list(self.target_overlap),
            "a_need_b_have": list(self.a_need_b_have),
            "b_need_a_have": list(self.b_need_a_have),
            "data_model_overlap": list(self.data_model_overlap),
            "access_pattern_overlap": list(self.access_pattern_overlap),
            "missing": list(self.missing),
            "evidence_used": list(self.evidence_used),
            "score": self.score,
        }


@dataclass(slots=True)
class RawPairProjector:
    """Project direct set relationships only; never collapse them into a score."""

    store: PrimitiveEvidenceStore

    @staticmethod
    def _intersection(left: tuple[str, ...] | None, right: tuple[str, ...] | None) -> tuple[str, ...]:
        if left is None or right is None:
            return ()
        return tuple(sorted(set(left).intersection(right)))

    def project(self, pair: PairCandidate) -> RawPairFeatures:
        left = self.store.latest(pair.repo_a_id)
        right = self.store.latest(pair.repo_b_id)

        missing: list[str] = []
        if left.observation_id is None:
            missing.append(f"{left.repo_id}:primitives")
        if right.observation_id is None:
            missing.append(f"{right.repo_id}:primitives")
        missing.extend(f"{left.repo_id}:{field}" for field in left.missing_fields)
        missing.extend(f"{right.repo_id}:{field}" for field in right.missing_fields)

        evidence_used = tuple(
            f"observation:{observation_id}"
            for observation_id in (left.observation_id, right.observation_id)
            if observation_id is not None
        )

        return RawPairFeatures(
            pair_id=pair.pair_id,
            repo_a_id=pair.repo_a_id,
            repo_b_id=pair.repo_b_id,
            shared_mechanisms=self._intersection(left.mechanisms, right.mechanisms),
            target_overlap=self._intersection(left.targets, right.targets),
            a_need_b_have=self._intersection(left.need, right.have),
            b_need_a_have=self._intersection(right.need, left.have),
            data_model_overlap=self._intersection(left.data_models, right.data_models),
            access_pattern_overlap=self._intersection(left.access_patterns, right.access_patterns),
            missing=tuple(missing),
            evidence_used=evidence_used,
        )
