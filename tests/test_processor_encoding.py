from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from archotraz.evidence import EvidenceLedger
from archotraz.processor_encoding import (
    ENCODED_FEATURES,
    DEFERRED_FEATURES,
    EncodingRunError,
    EpistemicallyBoundedCategoricalEncoder,
)


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


class ProcessorEncodingTests(unittest.TestCase):
    def make_ledger(self, root: str) -> EvidenceLedger:
        ledger = EvidenceLedger(Path(root) / "ledger.db")
        ledger.initialize()
        return ledger

    def matrix_payload(
        self,
        *,
        repo_ids: list[str] | None = None,
        values: list[list[object]] | None = None,
        missingness: list[list[bool]] | None = None,
        feature_names: list[str] | None = None,
    ) -> dict[str, object]:
        repo_ids = repo_ids or [
            "repo:github:example/alpha",
            "repo:github:example/bravo",
            "repo:github:example/charlie",
        ]
        feature_names = feature_names or list(SOURCE_FEATURES)
        values = values or [
            ["github", ["beta", "alpha"], "research", None, None, None, None, None, None, None, None],
            ["gitlab", [], None, None, None, None, None, None, None, None, None],
            [None, None, "high", None, None, None, None, None, None, None, None],
        ]
        missingness = missingness or [
            [False, False, False, True, True, True, True, True, True, True, True],
            [False, False, True, True, True, True, True, True, True, True, True],
            [True, True, False, True, True, True, True, True, True, True, True],
        ]
        return {
            "repo_record_ids": repo_ids,
            "feature_names": feature_names,
            "values": values,
            "missingness": missingness,
            "evidence_scope": "pre_intake",
            "completeness": "partial",
            "source_snapshot_ids": [f"snapshot-{index}" for index in range(len(repo_ids))],
        }

    def record_matrix(self, ledger: EvidenceLedger, payload: object | None = None, *, kind: str = "processor.feature_matrix") -> str:
        observation = ledger.record_observation(
            kind,
            "test.matrix",
            self.matrix_payload() if payload is None else payload,
            interpretation_status="derived_projection",
        )
        return observation.evidence_id

    def encoder(self, ledger: EvidenceLedger) -> EpistemicallyBoundedCategoricalEncoder:
        return EpistemicallyBoundedCategoricalEncoder(ledger)

    def test_unknown_matrix_id_fails_closed_and_records_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = self.make_ledger(tmp)
            with self.assertRaises(EncodingRunError):
                self.encoder(ledger).encode("missing-matrix")

            attempt = ledger.rows("attempts")[-1]
            self.assertEqual(attempt["kind"], "processor.categorical_encoding")
            self.assertEqual(attempt["status"], "failed")
            self.assertEqual(len(ledger.rows("failures")), 1)
            self.assertEqual(
                [row for row in ledger.rows("observations") if row["kind"] == "processor.encoded_feature_matrix"],
                [],
            )

    def test_wrong_observation_kind_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = self.make_ledger(tmp)
            observation_id = self.record_matrix(ledger, kind="processor.feature_snapshot")
            with self.assertRaises(EncodingRunError):
                self.encoder(ledger).encode(observation_id)

    def test_malformed_matrix_payload_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = self.make_ledger(tmp)
            observation_id = self.record_matrix(ledger, payload=["not", "a", "matrix"])
            with self.assertRaises(EncodingRunError):
                self.encoder(ledger).encode(observation_id)

    def test_row_count_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = self.make_ledger(tmp)
            payload = self.matrix_payload()
            payload["values"] = payload["values"][:-1]
            observation_id = self.record_matrix(ledger, payload)
            with self.assertRaises(EncodingRunError):
                self.encoder(ledger).encode(observation_id)

    def test_value_width_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = self.make_ledger(tmp)
            payload = self.matrix_payload()
            payload["values"][0] = payload["values"][0][:-1]
            observation_id = self.record_matrix(ledger, payload)
            with self.assertRaises(EncodingRunError):
                self.encoder(ledger).encode(observation_id)

    def test_missingness_width_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = self.make_ledger(tmp)
            payload = self.matrix_payload()
            payload["missingness"][0] = payload["missingness"][0][:-1]
            observation_id = self.record_matrix(ledger, payload)
            with self.assertRaises(EncodingRunError):
                self.encoder(ledger).encode(observation_id)

    def test_unexpected_source_feature_schema_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = self.make_ledger(tmp)
            payload = self.matrix_payload(feature_names=list(reversed(SOURCE_FEATURES)))
            observation_id = self.record_matrix(ledger, payload)
            with self.assertRaises(EncodingRunError):
                self.encoder(ledger).encode(observation_id)

    def test_invalid_provider_type_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = self.make_ledger(tmp)
            payload = self.matrix_payload()
            payload["values"][0][0] = 7
            observation_id = self.record_matrix(ledger, payload)
            with self.assertRaises(EncodingRunError):
                self.encoder(ledger).encode(observation_id)

    def test_invalid_tags_type_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = self.make_ledger(tmp)
            payload = self.matrix_payload()
            payload["values"][0][1] = "alpha"
            observation_id = self.record_matrix(ledger, payload)
            with self.assertRaises(EncodingRunError):
                self.encoder(ledger).encode(observation_id)

    def test_tags_non_string_member_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = self.make_ledger(tmp)
            payload = self.matrix_payload()
            payload["values"][0][1] = ["alpha", 3]
            observation_id = self.record_matrix(ledger, payload)
            with self.assertRaises(EncodingRunError):
                self.encoder(ledger).encode(observation_id)

    def test_invalid_priority_type_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = self.make_ledger(tmp)
            payload = self.matrix_payload()
            payload["values"][0][2] = ["research"]
            observation_id = self.record_matrix(ledger, payload)
            with self.assertRaises(EncodingRunError):
                self.encoder(ledger).encode(observation_id)

    def test_known_value_with_missingness_true_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = self.make_ledger(tmp)
            payload = self.matrix_payload()
            payload["missingness"][0][0] = True
            observation_id = self.record_matrix(ledger, payload)
            with self.assertRaises(EncodingRunError):
                self.encoder(ledger).encode(observation_id)

    def test_null_value_with_missingness_false_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = self.make_ledger(tmp)
            payload = self.matrix_payload()
            payload["values"][0][0] = None
            payload["missingness"][0][0] = False
            observation_id = self.record_matrix(ledger, payload)
            with self.assertRaises(EncodingRunError):
                self.encoder(ledger).encode(observation_id)

    def test_vocabulary_uses_only_known_values_and_excludes_synthetic_missing_categories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = self.make_ledger(tmp)
            matrix_id = self.record_matrix(ledger)
            result = self.encoder(ledger).encode(matrix_id)

            self.assertEqual(result.vocabularies["provider"], ("github", "gitlab"))
            self.assertEqual(result.vocabularies["tags"], ("alpha", "beta"))
            self.assertEqual(result.vocabularies["priority"], ("high", "research"))
            flattened = {value for vocabulary in result.vocabularies.values() for value in vocabulary}
            self.assertTrue({"null", "unknown", "missing"}.isdisjoint({value.casefold() for value in flattened}))

    def test_vocabulary_and_encoded_payload_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = self.make_ledger(tmp)
            matrix_id = self.record_matrix(ledger)
            encoder = self.encoder(ledger)
            first = encoder.encode(matrix_id)
            second = encoder.encode(matrix_id)

            self.assertEqual(first.normalized_payload(), second.normalized_payload())
            self.assertNotEqual(first.attempt_id, second.attempt_id)
            self.assertNotEqual(first.observation_id, second.observation_id)

    def test_provider_is_one_hot_encoded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = self.make_ledger(tmp)
            result = self.encoder(ledger).encode(self.record_matrix(ledger))
            github = result.encoded_feature_names.index("provider::github")
            gitlab = result.encoded_feature_names.index("provider::gitlab")

            self.assertEqual((result.encoded_values[0][github], result.encoded_values[0][gitlab]), (1, 0))
            self.assertEqual((result.encoded_values[1][github], result.encoded_values[1][gitlab]), (0, 1))

    def test_tags_are_multi_hot_encoded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = self.make_ledger(tmp)
            result = self.encoder(ledger).encode(self.record_matrix(ledger))
            alpha = result.encoded_feature_names.index("tags::alpha")
            beta = result.encoded_feature_names.index("tags::beta")

            self.assertEqual((result.encoded_values[0][alpha], result.encoded_values[0][beta]), (1, 1))
            self.assertEqual((result.encoded_missingness[0][alpha], result.encoded_missingness[0][beta]), (False, False))

    def test_known_empty_tags_are_zero_vector_not_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = self.make_ledger(tmp)
            result = self.encoder(ledger).encode(self.record_matrix(ledger))
            tag_indexes = [
                index for index, name in enumerate(result.encoded_feature_names) if name.startswith("tags::")
            ]

            self.assertTrue(tag_indexes)
            self.assertEqual([result.encoded_values[1][index] for index in tag_indexes], [0] * len(tag_indexes))
            self.assertEqual(
                [result.encoded_missingness[1][index] for index in tag_indexes],
                [False] * len(tag_indexes),
            )

    def test_priority_is_one_hot_and_unknown_is_null_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = self.make_ledger(tmp)
            result = self.encoder(ledger).encode(self.record_matrix(ledger))
            high = result.encoded_feature_names.index("priority::high")
            research = result.encoded_feature_names.index("priority::research")

            self.assertEqual((result.encoded_values[0][high], result.encoded_values[0][research]), (0, 1))
            self.assertEqual((result.encoded_values[1][high], result.encoded_values[1][research]), (None, None))
            self.assertEqual(
                (result.encoded_missingness[1][high], result.encoded_missingness[1][research]),
                (True, True),
            )

    def test_all_unknown_encoded_features_project_null_with_true_missingness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = self.make_ledger(tmp)
            payload = self.matrix_payload(
                repo_ids=["repo:github:example/unknown"],
                values=[[None, None, None, None, None, None, None, None, None, None, None]],
                missingness=[[True] * len(SOURCE_FEATURES)],
            )
            result = self.encoder(ledger).encode(self.record_matrix(ledger, payload))

            self.assertEqual(result.encoded_values, ((),))
            self.assertEqual(result.encoded_missingness, ((),))
            self.assertEqual(result.vocabularies, {"provider": (), "tags": (), "priority": ()})
            provider_index = result.source_feature_names.index("provider")
            tags_index = result.source_feature_names.index("tags")
            priority_index = result.source_feature_names.index("priority")
            self.assertTrue(result.source_missingness[0][provider_index])
            self.assertTrue(result.source_missingness[0][tags_index])
            self.assertTrue(result.source_missingness[0][priority_index])

    def test_deferred_features_are_never_encoded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = self.make_ledger(tmp)
            result = self.encoder(ledger).encode(self.record_matrix(ledger))

            self.assertEqual(result.encoded_features, ENCODED_FEATURES)
            self.assertEqual(result.deferred_features, DEFERRED_FEATURES)
            self.assertEqual(result.deferred_features, SOURCE_FEATURES[3:])
            for feature in result.deferred_features:
                self.assertFalse(any(name.startswith(f"{feature}::") for name in result.encoded_feature_names))

    def test_success_records_attempt_observation_and_exact_matrix_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = self.make_ledger(tmp)
            matrix_id = self.record_matrix(ledger)
            result = self.encoder(ledger).encode(matrix_id)

            attempt = ledger.rows("attempts")[-1]
            self.assertEqual(attempt["id"], result.attempt_id)
            self.assertEqual(attempt["kind"], "processor.categorical_encoding")
            self.assertEqual(attempt["status"], "succeeded")
            encoded = [row for row in ledger.rows("observations") if row["kind"] == "processor.encoded_feature_matrix"]
            self.assertEqual(len(encoded), 1)
            self.assertEqual(encoded[0]["id"], result.observation_id)
            provenance = [
                row for row in ledger.rows("provenance") if row["evidence_id"] == result.observation_id
            ]
            self.assertEqual(len(provenance), 1)
            self.assertEqual(provenance[0]["source_ref"], matrix_id)
            self.assertEqual(result.source_matrix_id, matrix_id)

    def test_failed_run_emits_no_partial_encoded_observation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = self.make_ledger(tmp)
            payload = self.matrix_payload()
            payload["values"][0][0] = 99
            matrix_id = self.record_matrix(ledger, payload)
            with self.assertRaises(EncodingRunError):
                self.encoder(ledger).encode(matrix_id)

            self.assertEqual(ledger.rows("attempts")[-1]["status"], "failed")
            self.assertEqual(len(ledger.rows("failures")), 1)
            self.assertEqual(
                [row for row in ledger.rows("observations") if row["kind"] == "processor.encoded_feature_matrix"],
                [],
            )

    def test_encoder_has_no_downstream_authority_or_acquisition(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = self.make_ledger(tmp)
            matrix_id = self.record_matrix(ledger)
            before_decisions = list(ledger.rows("decisions"))
            encoder = self.encoder(ledger)

            with patch("archotraz.processor.EpistemicallyBoundedProcessor.extract", side_effect=AssertionError("feature extraction forbidden")), patch(
                "archotraz.processor_matrix.EpistemicallyBoundedMatrixBuilder.build",
                side_effect=AssertionError("matrix construction forbidden"),
            ), patch("archotraz.cells.CellHousing.current", side_effect=AssertionError("cell access forbidden")), patch(
                "archotraz.cells.CellHousing.place", side_effect=AssertionError("placement forbidden")
            ), patch("archotraz.cells.CellHousing.move", side_effect=AssertionError("movement forbidden")), patch(
                "archotraz.guards.PairEnumerationGuard.run", side_effect=AssertionError("guard execution forbidden")
            ), patch("urllib.request.urlopen", side_effect=AssertionError("network access forbidden")), patch.object(
                Path, "read_text", side_effect=AssertionError("source read forbidden")
            ), patch.object(Path, "read_bytes", side_effect=AssertionError("source read forbidden")):
                result = encoder.encode(matrix_id)

            self.assertEqual(ledger.rows("decisions"), before_decisions)
            serialized = json.dumps(result.normalized_payload(), sort_keys=True).lower()
            for forbidden in ("score", "rank", "classif", "recommend", "admit", "reject", "placement", "guard"):
                self.assertNotIn(forbidden, serialized)
            for method in ("score", "rank", "classify", "recommend", "admit", "reject", "place", "move", "run_guard"):
                self.assertFalse(hasattr(encoder, method))


if __name__ == "__main__":
    unittest.main()
