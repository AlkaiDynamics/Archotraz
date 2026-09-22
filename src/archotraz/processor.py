from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from typing import Any

from .evidence import EvidenceLedger


PROCESSOR_ATTEMPT_KIND = "processor.feature_extraction"
PROCESSOR_OBSERVATION_KIND = "processor.feature_snapshot"
UNKNOWN_CANONICAL_FEATURES = (
    "mechanisms",
    "targets",
    "have",
    "need",
    "DataModel",
    "AccessPattern",
    "fidelity",
    "debt",
)


class ProcessorRunError(ValueError):
    pass


class FeatureState(str, Enum):
    OBSERVED = "observed"
    DECLARED = "declared"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class FeatureValue:
    name: str
    value: Any
    state: FeatureState
    evidence_basis: tuple[str, ...]

    def to_payload(self) -> dict[str, Any]:
        value = list(self.value) if isinstance(self.value, tuple) else self.value
        return {
            "value": value,
            "state": self.state.value,
            "evidence_basis": list(self.evidence_basis),
        }


@dataclass(frozen=True, slots=True)
class FeatureSnapshot:
    repo_record_id: str
    evidence_scope: str
    completeness: str
    features: tuple[FeatureValue, ...]
    missingness: dict[str, bool]
    evidence_basis: tuple[str, ...]
    attempt_id: str
    observation_id: str

    def feature(self, name: str) -> FeatureValue:
        for feature in self.features:
            if feature.name == name:
                return feature
        raise KeyError(name)

    def normalized_payload(self) -> dict[str, Any]:
        return {
            "repo_record_id": self.repo_record_id,
            "evidence_scope": self.evidence_scope,
            "completeness": self.completeness,
            "features": {feature.name: feature.to_payload() for feature in self.features},
            "missingness": dict(self.missingness),
            "evidence_basis": list(self.evidence_basis),
        }

    def to_payload(self) -> dict[str, Any]:
        payload = self.normalized_payload()
        payload["attempt_id"] = self.attempt_id
        payload["observation_id"] = self.observation_id
        return payload


class EpistemicallyBoundedProcessor:
    """Normalize existing canonical evidence without acquiring or deciding anything.

    This first Processor slice is explicitly PRE_INTAKE and PARTIAL. It consumes
    only existing RepoRecord and Detective observations. It does not inspect source,
    fetch metadata, make placement decisions, invoke Guards, score, rank, admit,
    reject, or infer unsupported canonical features.
    """

    name = "epistemically_bounded_feature_extraction"

    def __init__(self, ledger: EvidenceLedger):
        self.ledger = ledger

    def extract(self, repo_record_id: str) -> FeatureSnapshot:
        candidate = str(repo_record_id).strip()
        attempt_id = self.ledger.begin_attempt(
            PROCESSOR_ATTEMPT_KIND,
            {"repo_record_id": candidate},
        )
        try:
            if not candidate:
                raise ProcessorRunError("repo_record_id is required")

            repo_row = self._require_single_observation("repo.record", candidate)
            detective_row = self._require_single_observation("detective.triage", candidate)

            repo_payload = self._payload(repo_row, "repo.record")
            detective_payload = self._payload(detective_row, "detective.triage")
            if repo_payload.get("record_id") != candidate:
                raise ProcessorRunError(f"repo.record evidence identity mismatch: {candidate}")
            if detective_payload.get("record_id") != candidate:
                raise ProcessorRunError(f"detective.triage evidence identity mismatch: {candidate}")

            repo_evidence_id = str(repo_row["id"])
            detective_evidence_id = str(detective_row["id"])
            features = self._features(repo_payload, repo_evidence_id)
            missingness = {
                feature.name: feature.state is FeatureState.UNKNOWN
                for feature in features
            }
            evidence_basis = (repo_evidence_id, detective_evidence_id)
            normalized = {
                "repo_record_id": candidate,
                "evidence_scope": "pre_intake",
                "completeness": "partial",
                "features": {feature.name: feature.to_payload() for feature in features},
                "missingness": missingness,
                "evidence_basis": list(evidence_basis),
            }

            observation = self.ledger.record_observation(
                PROCESSOR_OBSERVATION_KIND,
                "archotraz.processor",
                normalized,
                external_ref=candidate,
                interpretation_status="derived_normalization",
            )
            for role, source_ref in (
                ("repo_record", repo_evidence_id),
                ("detective_triage", detective_evidence_id),
            ):
                self.ledger.record_provenance(
                    observation,
                    source_type="observation",
                    source_ref=source_ref,
                    metadata={"role": role, "processor": self.name},
                )

            snapshot = FeatureSnapshot(
                repo_record_id=candidate,
                evidence_scope="pre_intake",
                completeness="partial",
                features=features,
                missingness=missingness,
                evidence_basis=evidence_basis,
                attempt_id=attempt_id,
                observation_id=observation.evidence_id,
            )
            self.ledger.finish_attempt(
                attempt_id,
                status="succeeded",
                output=snapshot.to_payload(),
            )
            return snapshot
        except Exception as exc:
            error = exc if isinstance(exc, ProcessorRunError) else ProcessorRunError(str(exc))
            self.ledger.finish_attempt(attempt_id, status="failed", error_text=str(error))
            self.ledger.record_failure(
                PROCESSOR_ATTEMPT_KIND,
                str(error),
                attempt_id=attempt_id,
                payload={"repo_record_id": candidate},
            )
            raise error from None

    def _require_single_observation(self, kind: str, repo_record_id: str) -> dict[str, Any]:
        matches = [
            row
            for row in self.ledger.rows("observations")
            if row["kind"] == kind and row["external_ref"] == repo_record_id
        ]
        if not matches:
            raise ProcessorRunError(f"required upstream evidence missing: {kind} for {repo_record_id}")
        if len(matches) != 1:
            raise ProcessorRunError(f"ambiguous upstream evidence: {kind} for {repo_record_id}")
        return matches[0]

    @staticmethod
    def _payload(row: dict[str, Any], kind: str) -> dict[str, Any]:
        try:
            payload = json.loads(str(row["payload_json"]))
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ProcessorRunError(f"invalid upstream payload: {kind}") from exc
        if not isinstance(payload, dict):
            raise ProcessorRunError(f"invalid upstream payload: {kind}")
        return payload

    @staticmethod
    def _features(repo_payload: dict[str, Any], repo_evidence_id: str) -> tuple[FeatureValue, ...]:
        provider = repo_payload.get("provider")
        if not isinstance(provider, str) or not provider.strip():
            raise ProcessorRunError("repo.record provider evidence is missing")

        raw_tags = repo_payload.get("tags", [])
        if not isinstance(raw_tags, list):
            raise ProcessorRunError("repo.record tags evidence must be a list")
        tags = tuple(str(tag) for tag in raw_tags)

        priority = repo_payload.get("priority")
        priority_feature = FeatureValue(
            name="priority",
            value=priority,
            state=FeatureState.DECLARED if priority is not None else FeatureState.UNKNOWN,
            evidence_basis=(repo_evidence_id,) if priority is not None else (),
        )

        known = (
            FeatureValue(
                name="provider",
                value=provider.strip().casefold(),
                state=FeatureState.OBSERVED,
                evidence_basis=(repo_evidence_id,),
            ),
            FeatureValue(
                name="tags",
                value=tags,
                state=FeatureState.DECLARED,
                evidence_basis=(repo_evidence_id,),
            ),
            priority_feature,
        )
        unknown = tuple(
            FeatureValue(
                name=name,
                value=None,
                state=FeatureState.UNKNOWN,
                evidence_basis=(),
            )
            for name in UNKNOWN_CANONICAL_FEATURES
        )
        return known + unknown
