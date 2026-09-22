from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Iterable

from .evidence import EvidenceLedger


MATRIX_ATTEMPT_KIND = "processor.feature_matrix_projection"
MATRIX_OBSERVATION_KIND = "processor.feature_matrix"
SNAPSHOT_OBSERVATION_KIND = "processor.feature_snapshot"
FEATURE_COLUMNS = (
    "provider",
    "tags",
    "priority",
    "mechanisms",
    "targets",
    "have",
    "need",
    "DataModel",
    "AccessPattern",
    "fidelity",
    "debt",
)


class MatrixRunError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class _ValidatedSnapshot:
    observation_id: str
    repo_record_id: str
    evidence_scope: str
    completeness: str
    values: tuple[Any, ...]
    missingness: tuple[bool, ...]


@dataclass(frozen=True, slots=True)
class FeatureMatrixSnapshot:
    repo_record_ids: tuple[str, ...]
    feature_names: tuple[str, ...]
    values: tuple[tuple[Any, ...], ...]
    missingness: tuple[tuple[bool, ...], ...]
    evidence_scope: str
    completeness: str
    source_snapshot_ids: tuple[str, ...]
    attempt_id: str
    observation_id: str

    def normalized_payload(self) -> dict[str, Any]:
        return {
            "repo_record_ids": list(self.repo_record_ids),
            "feature_names": list(self.feature_names),
            "values": [list(row) for row in self.values],
            "missingness": [list(row) for row in self.missingness],
            "evidence_scope": self.evidence_scope,
            "completeness": self.completeness,
            "source_snapshot_ids": list(self.source_snapshot_ids),
        }

    def to_payload(self) -> dict[str, Any]:
        payload = self.normalized_payload()
        payload["attempt_id"] = self.attempt_id
        payload["observation_id"] = self.observation_id
        return payload


class EpistemicallyBoundedMatrixBuilder:
    """Project explicit Processor snapshots into rectangular X/M state only.

    The builder consumes already-recorded processor.feature_snapshot observations.
    It does not extract features, inspect repository source, acquire metadata, impute
    missing values, encode categories numerically, make decisions, inspect Cell
    Housing, invoke Guards, score, rank, classify, recommend, admit, or reject.
    """

    name = "epistemically_bounded_feature_matrix"

    def __init__(self, ledger: EvidenceLedger):
        self.ledger = ledger

    def build(self, snapshot_observation_ids: Iterable[str]) -> FeatureMatrixSnapshot:
        raw_ids = [str(value).strip() for value in snapshot_observation_ids]
        attempt_id = self.ledger.begin_attempt(
            MATRIX_ATTEMPT_KIND,
            {"snapshot_observation_ids": raw_ids},
        )
        try:
            if not raw_ids or any(not value for value in raw_ids):
                raise MatrixRunError("at least one explicit feature snapshot observation id is required")
            if len(set(raw_ids)) != len(raw_ids):
                raise MatrixRunError("duplicate feature snapshot observation ids are not allowed")

            observation_rows = {str(row["id"]): row for row in self.ledger.rows("observations")}
            snapshots = [self._validate_snapshot(observation_rows.get(snapshot_id), snapshot_id) for snapshot_id in raw_ids]

            repo_ids = [snapshot.repo_record_id for snapshot in snapshots]
            if len(set(repo_ids)) != len(repo_ids):
                raise MatrixRunError("multiple selected feature snapshots represent the same repository")

            scopes = {snapshot.evidence_scope for snapshot in snapshots}
            if len(scopes) != 1:
                raise MatrixRunError("selected feature snapshots have mixed evidence_scope values")
            completeness_values = {snapshot.completeness for snapshot in snapshots}
            if len(completeness_values) != 1:
                raise MatrixRunError("selected feature snapshots have mixed completeness values")

            ordered = tuple(sorted(snapshots, key=lambda snapshot: snapshot.repo_record_id))
            evidence_scope = ordered[0].evidence_scope
            completeness = ordered[0].completeness
            normalized = {
                "repo_record_ids": [snapshot.repo_record_id for snapshot in ordered],
                "feature_names": list(FEATURE_COLUMNS),
                "values": [list(snapshot.values) for snapshot in ordered],
                "missingness": [list(snapshot.missingness) for snapshot in ordered],
                "evidence_scope": evidence_scope,
                "completeness": completeness,
                "source_snapshot_ids": [snapshot.observation_id for snapshot in ordered],
            }

            observation = self.ledger.record_observation(
                MATRIX_OBSERVATION_KIND,
                "archotraz.processor_matrix",
                normalized,
                interpretation_status="derived_projection",
            )
            for row_index, snapshot in enumerate(ordered):
                self.ledger.record_provenance(
                    observation,
                    source_type="processor_feature_snapshot",
                    source_ref=snapshot.observation_id,
                    metadata={
                        "repo_record_id": snapshot.repo_record_id,
                        "row_index": row_index,
                    },
                )

            result = FeatureMatrixSnapshot(
                repo_record_ids=tuple(snapshot.repo_record_id for snapshot in ordered),
                feature_names=FEATURE_COLUMNS,
                values=tuple(snapshot.values for snapshot in ordered),
                missingness=tuple(snapshot.missingness for snapshot in ordered),
                evidence_scope=evidence_scope,
                completeness=completeness,
                source_snapshot_ids=tuple(snapshot.observation_id for snapshot in ordered),
                attempt_id=attempt_id,
                observation_id=observation.evidence_id,
            )
            self.ledger.finish_attempt(attempt_id, status="succeeded", output=result.to_payload())
            return result
        except Exception as exc:
            error = exc if isinstance(exc, MatrixRunError) else MatrixRunError(str(exc))
            self.ledger.finish_attempt(attempt_id, status="failed", error_text=str(error))
            self.ledger.record_failure(
                MATRIX_ATTEMPT_KIND,
                str(error),
                attempt_id=attempt_id,
                payload={"snapshot_observation_ids": raw_ids},
            )
            raise error from None

    def _validate_snapshot(self, row: dict[str, Any] | None, snapshot_id: str) -> _ValidatedSnapshot:
        if row is None:
            raise MatrixRunError(f"feature snapshot observation not found: {snapshot_id}")
        if row.get("kind") != SNAPSHOT_OBSERVATION_KIND:
            raise MatrixRunError(f"observation is not a feature snapshot: {snapshot_id}")

        payload = self._payload(row, snapshot_id)
        repo_record_id = payload.get("repo_record_id")
        evidence_scope = payload.get("evidence_scope")
        completeness = payload.get("completeness")
        features = payload.get("features")
        missingness = payload.get("missingness")

        if not isinstance(repo_record_id, str) or not repo_record_id.strip():
            raise MatrixRunError(f"feature snapshot repo_record_id is invalid: {snapshot_id}")
        if row.get("external_ref") not in {None, repo_record_id}:
            raise MatrixRunError(f"feature snapshot identity mismatch: {snapshot_id}")
        if not isinstance(evidence_scope, str) or not evidence_scope.strip():
            raise MatrixRunError(f"feature snapshot evidence_scope is invalid: {snapshot_id}")
        if not isinstance(completeness, str) or not completeness.strip():
            raise MatrixRunError(f"feature snapshot completeness is invalid: {snapshot_id}")
        if not isinstance(features, dict) or set(features) != set(FEATURE_COLUMNS):
            raise MatrixRunError(f"feature snapshot schema mismatch: {snapshot_id}")
        if not isinstance(missingness, dict) or set(missingness) != set(FEATURE_COLUMNS):
            raise MatrixRunError(f"feature snapshot missingness schema mismatch: {snapshot_id}")

        values: list[Any] = []
        mask: list[bool] = []
        for name in FEATURE_COLUMNS:
            feature = features[name]
            missing = missingness[name]
            if not isinstance(feature, dict):
                raise MatrixRunError(f"feature payload is invalid for {name}: {snapshot_id}")
            if set(feature) != {"value", "state", "evidence_basis"}:
                raise MatrixRunError(f"feature payload schema mismatch for {name}: {snapshot_id}")
            if feature["state"] not in {"observed", "declared", "unknown"}:
                raise MatrixRunError(f"feature state is invalid for {name}: {snapshot_id}")
            if not isinstance(feature["evidence_basis"], list):
                raise MatrixRunError(f"feature evidence basis is invalid for {name}: {snapshot_id}")
            if not isinstance(missing, bool):
                raise MatrixRunError(f"missingness value is invalid for {name}: {snapshot_id}")

            value = feature["value"]
            if feature["state"] == "unknown":
                if value is not None or missing is not True:
                    raise MatrixRunError(f"UNKNOWN must project from null value with true missingness: {name}")
            else:
                if missing is not False or value is None:
                    raise MatrixRunError(f"known feature must have a value with false missingness: {name}")

            values.append(value)
            mask.append(missing)

        return _ValidatedSnapshot(
            observation_id=snapshot_id,
            repo_record_id=repo_record_id.strip(),
            evidence_scope=evidence_scope.strip(),
            completeness=completeness.strip(),
            values=tuple(values),
            missingness=tuple(mask),
        )

    @staticmethod
    def _payload(row: dict[str, Any], snapshot_id: str) -> dict[str, Any]:
        try:
            payload = json.loads(str(row["payload_json"]))
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise MatrixRunError(f"feature snapshot payload is malformed: {snapshot_id}") from exc
        if not isinstance(payload, dict):
            raise MatrixRunError(f"feature snapshot payload is malformed: {snapshot_id}")
        return payload
