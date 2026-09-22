from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from .evidence import EvidenceLedger


ENCODING_ATTEMPT_KIND = "processor.categorical_encoding"
ENCODING_OBSERVATION_KIND = "processor.encoded_feature_matrix"
MATRIX_OBSERVATION_KIND = "processor.feature_matrix"
SOURCE_FEATURES = (
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
ENCODED_FEATURES = ("provider", "tags", "priority")
DEFERRED_FEATURES = SOURCE_FEATURES[len(ENCODED_FEATURES) :]


class EncodingRunError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class EncodedFeatureMatrixSnapshot:
    repo_record_ids: tuple[str, ...]
    encoded_feature_names: tuple[str, ...]
    encoded_feature_sources: tuple[str, ...]
    encoded_values: tuple[tuple[int | None, ...], ...]
    encoded_missingness: tuple[tuple[bool, ...], ...]
    source_feature_names: tuple[str, ...]
    source_missingness: tuple[tuple[bool, ...], ...]
    vocabularies: dict[str, tuple[str, ...]]
    encoded_features: tuple[str, ...]
    deferred_features: tuple[str, ...]
    evidence_scope: str
    completeness: str
    source_matrix_id: str
    attempt_id: str
    observation_id: str

    def normalized_payload(self) -> dict[str, Any]:
        return {
            "repo_record_ids": list(self.repo_record_ids),
            "encoded_feature_names": list(self.encoded_feature_names),
            "encoded_feature_sources": list(self.encoded_feature_sources),
            "encoded_values": [list(row) for row in self.encoded_values],
            "encoded_missingness": [list(row) for row in self.encoded_missingness],
            "source_feature_names": list(self.source_feature_names),
            "source_missingness": [list(row) for row in self.source_missingness],
            "vocabularies": {
                name: list(self.vocabularies[name]) for name in ENCODED_FEATURES
            },
            "encoded_features": list(self.encoded_features),
            "deferred_features": list(self.deferred_features),
            "evidence_scope": self.evidence_scope,
            "completeness": self.completeness,
            "source_matrix_id": self.source_matrix_id,
        }

    def to_payload(self) -> dict[str, Any]:
        payload = self.normalized_payload()
        payload["attempt_id"] = self.attempt_id
        payload["observation_id"] = self.observation_id
        return payload


@dataclass(frozen=True, slots=True)
class _ValidatedMatrix:
    repo_record_ids: tuple[str, ...]
    values: tuple[tuple[Any, ...], ...]
    missingness: tuple[tuple[bool, ...], ...]
    evidence_scope: str
    completeness: str


class EpistemicallyBoundedCategoricalEncoder:
    """Encode only established categorical identity from one explicit matrix artifact.

    This stage consumes an already-recorded processor.feature_matrix observation.
    It does not extract features, build matrices, acquire evidence, inspect source,
    impute unknowns, weight categories, score, rank, classify, recommend, make Cell
    Housing decisions, invoke Guards, admit, or reject.
    """

    name = "epistemically_bounded_categorical_encoding"

    def __init__(self, ledger: EvidenceLedger):
        self.ledger = ledger

    def encode(self, matrix_observation_id: str) -> EncodedFeatureMatrixSnapshot:
        matrix_id = str(matrix_observation_id).strip()
        attempt_id = self.ledger.begin_attempt(
            ENCODING_ATTEMPT_KIND,
            {"matrix_observation_id": matrix_id},
        )
        try:
            if not matrix_id:
                raise EncodingRunError("matrix_observation_id is required")

            row = self._require_matrix_observation(matrix_id)
            matrix = self._validate_matrix(row, matrix_id)
            vocabularies = self._derive_vocabularies(matrix)
            encoded_feature_names, encoded_feature_sources = self._encoded_columns(vocabularies)
            encoded_values, encoded_missingness = self._encode_rows(matrix, vocabularies)

            normalized = {
                "repo_record_ids": list(matrix.repo_record_ids),
                "encoded_feature_names": list(encoded_feature_names),
                "encoded_feature_sources": list(encoded_feature_sources),
                "encoded_values": [list(encoded_row) for encoded_row in encoded_values],
                "encoded_missingness": [list(mask_row) for mask_row in encoded_missingness],
                "source_feature_names": list(SOURCE_FEATURES),
                "source_missingness": [list(mask_row) for mask_row in matrix.missingness],
                "vocabularies": {
                    name: list(vocabularies[name]) for name in ENCODED_FEATURES
                },
                "encoded_features": list(ENCODED_FEATURES),
                "deferred_features": list(DEFERRED_FEATURES),
                "evidence_scope": matrix.evidence_scope,
                "completeness": matrix.completeness,
                "source_matrix_id": matrix_id,
            }
            observation = self.ledger.record_observation(
                ENCODING_OBSERVATION_KIND,
                "archotraz.processor_encoding",
                normalized,
                external_ref=matrix_id,
                interpretation_status="derived_encoding",
            )
            self.ledger.record_provenance(
                observation,
                source_type="processor_feature_matrix",
                source_ref=matrix_id,
                metadata={"encoder": self.name},
            )

            result = EncodedFeatureMatrixSnapshot(
                repo_record_ids=matrix.repo_record_ids,
                encoded_feature_names=encoded_feature_names,
                encoded_feature_sources=encoded_feature_sources,
                encoded_values=encoded_values,
                encoded_missingness=encoded_missingness,
                source_feature_names=SOURCE_FEATURES,
                source_missingness=matrix.missingness,
                vocabularies=vocabularies,
                encoded_features=ENCODED_FEATURES,
                deferred_features=DEFERRED_FEATURES,
                evidence_scope=matrix.evidence_scope,
                completeness=matrix.completeness,
                source_matrix_id=matrix_id,
                attempt_id=attempt_id,
                observation_id=observation.evidence_id,
            )
            self.ledger.finish_attempt(attempt_id, status="succeeded", output=result.to_payload())
            return result
        except Exception as exc:
            error = exc if isinstance(exc, EncodingRunError) else EncodingRunError(str(exc))
            self.ledger.finish_attempt(attempt_id, status="failed", error_text=str(error))
            self.ledger.record_failure(
                ENCODING_ATTEMPT_KIND,
                str(error),
                attempt_id=attempt_id,
                payload={"matrix_observation_id": matrix_id},
            )
            raise error from None

    def _require_matrix_observation(self, matrix_id: str) -> dict[str, Any]:
        matches = [row for row in self.ledger.rows("observations") if row["id"] == matrix_id]
        if not matches:
            raise EncodingRunError(f"feature matrix observation not found: {matrix_id}")
        row = matches[0]
        if row.get("kind") != MATRIX_OBSERVATION_KIND:
            raise EncodingRunError(f"observation is not a feature matrix: {matrix_id}")
        return row

    def _validate_matrix(self, row: dict[str, Any], matrix_id: str) -> _ValidatedMatrix:
        payload = self._payload(row, matrix_id)
        repo_record_ids = payload.get("repo_record_ids")
        feature_names = payload.get("feature_names")
        values = payload.get("values")
        missingness = payload.get("missingness")
        evidence_scope = payload.get("evidence_scope")
        completeness = payload.get("completeness")
        source_snapshot_ids = payload.get("source_snapshot_ids")

        if not isinstance(repo_record_ids, list) or not repo_record_ids:
            raise EncodingRunError("feature matrix repo_record_ids are invalid")
        if any(not isinstance(value, str) or not value.strip() for value in repo_record_ids):
            raise EncodingRunError("feature matrix repo_record_ids are invalid")
        if len(set(repo_record_ids)) != len(repo_record_ids):
            raise EncodingRunError("feature matrix contains duplicate repository rows")
        if feature_names != list(SOURCE_FEATURES):
            raise EncodingRunError("feature matrix source feature schema is unexpected")
        if not isinstance(values, list) or len(values) != len(repo_record_ids):
            raise EncodingRunError("feature matrix values row count is invalid")
        if not isinstance(missingness, list) or len(missingness) != len(repo_record_ids):
            raise EncodingRunError("feature matrix missingness row count is invalid")
        if not isinstance(evidence_scope, str) or not evidence_scope.strip():
            raise EncodingRunError("feature matrix evidence_scope is invalid")
        if not isinstance(completeness, str) or not completeness.strip():
            raise EncodingRunError("feature matrix completeness is invalid")
        if not isinstance(source_snapshot_ids, list) or len(source_snapshot_ids) != len(repo_record_ids):
            raise EncodingRunError("feature matrix source_snapshot_ids are invalid")
        if any(not isinstance(value, str) or not value.strip() for value in source_snapshot_ids):
            raise EncodingRunError("feature matrix source_snapshot_ids are invalid")

        validated_values: list[tuple[Any, ...]] = []
        validated_missingness: list[tuple[bool, ...]] = []
        for row_index, (value_row, mask_row) in enumerate(zip(values, missingness)):
            if not isinstance(value_row, list) or len(value_row) != len(SOURCE_FEATURES):
                raise EncodingRunError(f"feature matrix value width is invalid at row {row_index}")
            if not isinstance(mask_row, list) or len(mask_row) != len(SOURCE_FEATURES):
                raise EncodingRunError(f"feature matrix missingness width is invalid at row {row_index}")
            if any(not isinstance(value, bool) for value in mask_row):
                raise EncodingRunError(f"feature matrix missingness value is invalid at row {row_index}")

            for feature_index, (value, missing) in enumerate(zip(value_row, mask_row)):
                feature_name = SOURCE_FEATURES[feature_index]
                if missing and value is not None:
                    raise EncodingRunError(
                        f"known value cannot have source missingness=true: {feature_name}"
                    )
                if not missing and value is None:
                    raise EncodingRunError(
                        f"null value cannot have source missingness=false: {feature_name}"
                    )

            self._validate_encoded_types(value_row, mask_row, row_index)
            validated_values.append(tuple(value_row))
            validated_missingness.append(tuple(mask_row))

        return _ValidatedMatrix(
            repo_record_ids=tuple(repo_record_ids),
            values=tuple(validated_values),
            missingness=tuple(validated_missingness),
            evidence_scope=evidence_scope.strip(),
            completeness=completeness.strip(),
        )

    @staticmethod
    def _validate_encoded_types(value_row: list[Any], mask_row: list[bool], row_index: int) -> None:
        provider = value_row[0]
        tags = value_row[1]
        priority = value_row[2]

        if not mask_row[0] and (not isinstance(provider, str) or not provider.strip()):
            raise EncodingRunError(f"provider categorical value is invalid at row {row_index}")
        if not mask_row[1]:
            if not isinstance(tags, list):
                raise EncodingRunError(f"tags categorical value is invalid at row {row_index}")
            if any(not isinstance(tag, str) or not tag.strip() for tag in tags):
                raise EncodingRunError(f"tags categorical member is invalid at row {row_index}")
        if not mask_row[2] and (not isinstance(priority, str) or not priority.strip()):
            raise EncodingRunError(f"priority categorical value is invalid at row {row_index}")

    @staticmethod
    def _payload(row: dict[str, Any], matrix_id: str) -> dict[str, Any]:
        try:
            payload = json.loads(str(row["payload_json"]))
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise EncodingRunError(f"feature matrix payload is malformed: {matrix_id}") from exc
        if not isinstance(payload, dict):
            raise EncodingRunError(f"feature matrix payload is malformed: {matrix_id}")
        return payload

    @staticmethod
    def _derive_vocabularies(matrix: _ValidatedMatrix) -> dict[str, tuple[str, ...]]:
        providers: set[str] = set()
        tags: set[str] = set()
        priorities: set[str] = set()
        for value_row, mask_row in zip(matrix.values, matrix.missingness):
            if not mask_row[0]:
                providers.add(str(value_row[0]))
            if not mask_row[1]:
                tags.update(str(tag) for tag in value_row[1])
            if not mask_row[2]:
                priorities.add(str(value_row[2]))
        return {
            "provider": tuple(sorted(providers)),
            "tags": tuple(sorted(tags)),
            "priority": tuple(sorted(priorities)),
        }

    @staticmethod
    def _encoded_columns(
        vocabularies: dict[str, tuple[str, ...]],
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        names: list[str] = []
        sources: list[str] = []
        for feature in ENCODED_FEATURES:
            for category in vocabularies[feature]:
                names.append(f"{feature}::{category}")
                sources.append(feature)
        return tuple(names), tuple(sources)

    @staticmethod
    def _encode_rows(
        matrix: _ValidatedMatrix,
        vocabularies: dict[str, tuple[str, ...]],
    ) -> tuple[tuple[tuple[int | None, ...], ...], tuple[tuple[bool, ...], ...]]:
        encoded_rows: list[tuple[int | None, ...]] = []
        encoded_masks: list[tuple[bool, ...]] = []
        for value_row, mask_row in zip(matrix.values, matrix.missingness):
            values: list[int | None] = []
            mask: list[bool] = []
            for feature_index, feature in enumerate(ENCODED_FEATURES):
                vocabulary = vocabularies[feature]
                if mask_row[feature_index]:
                    values.extend([None] * len(vocabulary))
                    mask.extend([True] * len(vocabulary))
                    continue

                source_value = value_row[feature_index]
                if feature == "tags":
                    present = set(source_value)
                    values.extend(1 if category in present else 0 for category in vocabulary)
                else:
                    values.extend(1 if category == source_value else 0 for category in vocabulary)
                mask.extend([False] * len(vocabulary))
            encoded_rows.append(tuple(values))
            encoded_masks.append(tuple(mask))
        return tuple(encoded_rows), tuple(encoded_masks)
