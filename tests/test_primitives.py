from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from archotraz.evidence import EvidenceLedger
from archotraz.guards import PairCandidate
from archotraz.primitives import PrimitiveEvidenceStore, RawPairProjector
from archotraz.repos import RepoRegistry


class PrimitiveEvidenceTests(unittest.TestCase):
    def make_subjects(self, root: str):
        ledger = EvidenceLedger(Path(root) / "ledger.db")
        ledger.initialize()
        registry = RepoRegistry(ledger)
        store = PrimitiveEvidenceStore(ledger=ledger, registry=registry)
        return ledger, registry, store

    def test_primitive_profile_preserves_unknown_separately_from_explicit_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, registry, store = self.make_subjects(tmp)
            repo = registry.add_manual("https://github.com/AlkaiDynamics/Archotraz").record

            evidence = store.record(
                repo.repo_id,
                mechanisms=("parser", "parser"),
                have=(),
                source="manual",
                source_ref="operator:test",
            )
            profile = store.latest(repo.repo_id)

            self.assertEqual(profile.observation_id, evidence.evidence_id)
            self.assertEqual(profile.mechanisms, ("parser",))
            self.assertEqual(profile.have, ())
            self.assertIsNone(profile.targets)
            self.assertIsNone(profile.need)
            self.assertIsNone(profile.data_models)
            self.assertIsNone(profile.access_patterns)
            self.assertEqual(
                set(profile.missing_fields),
                {"targets", "need", "data_models", "access_patterns", "fidelity", "debt"},
            )

    def test_raw_pair_projection_uses_only_explicit_intersections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, registry, store = self.make_subjects(tmp)
            left = registry.add_manual("https://github.com/AlkaiDynamics/Archotraz").record
            right = registry.add_manual("https://github.com/openai/openai-python").record

            store.record(
                left.repo_id,
                mechanisms=("parser", "ledger"),
                targets=("repository",),
                have=("python",),
                need=("sqlite",),
                data_models=("json",),
                access_patterns=("cli",),
                fidelity=0.9,
                debt=0.2,
                source="manual",
                source_ref="operator:left",
            )
            store.record(
                right.repo_id,
                mechanisms=("parser", "http-client"),
                targets=("repository", "api"),
                have=("sqlite",),
                need=("python",),
                data_models=("json", "http"),
                access_patterns=("cli", "http"),
                fidelity=0.8,
                debt=0.3,
                source="manual",
                source_ref="operator:right",
            )

            pair = PairCandidate(left.repo_id, right.repo_id)
            features = RawPairProjector(store).project(pair)

            self.assertEqual(features.shared_mechanisms, ("parser",))
            self.assertEqual(features.target_overlap, ("repository",))
            if pair.repo_a_id == left.repo_id:
                self.assertEqual(features.a_need_b_have, ("sqlite",))
                self.assertEqual(features.b_need_a_have, ("python",))
            else:
                self.assertEqual(features.a_need_b_have, ("python",))
                self.assertEqual(features.b_need_a_have, ("sqlite",))
            self.assertEqual(features.data_model_overlap, ("json",))
            self.assertEqual(features.access_pattern_overlap, ("cli",))
            self.assertEqual(features.missing, ())
            self.assertIsNone(features.score)

    def test_raw_pair_projection_marks_unobserved_primitives_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, registry, store = self.make_subjects(tmp)
            left = registry.add_manual("https://github.com/AlkaiDynamics/Archotraz").record
            right = registry.add_manual("https://github.com/openai/openai-python").record

            store.record(
                left.repo_id,
                mechanisms=("ledger",),
                source="manual",
                source_ref="operator:left",
            )

            features = RawPairProjector(store).project(PairCandidate(left.repo_id, right.repo_id))

            self.assertIn(f"{left.repo_id}:need", features.missing)
            self.assertIn(f"{right.repo_id}:primitives", features.missing)
            self.assertEqual(features.a_need_b_have, ())
            self.assertEqual(features.b_need_a_have, ())
            self.assertIsNone(features.score)


if __name__ == "__main__":
    unittest.main()
