from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from archotraz.evidence import EvidenceLedger
from archotraz.processor import EpistemicallyBoundedProcessor
from archotraz.processor_matrix import EpistemicallyBoundedMatrixBuilder
from archotraz.repositories import ManualRepositoryIngestor


ROOT = Path(__file__).resolve().parents[1]


class CasePreviewTests(unittest.TestCase):
    def test_cold_start_preview_is_read_only_and_preserves_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "ledger.db"
            ledger = EvidenceLedger(db)
            ledger.initialize()
            repo = ManualRepositoryIngestor(ledger, dry_mode=True).ingest("https://github.com/example/alpha").record.record_id
            snapshot = EpistemicallyBoundedProcessor(ledger).extract(repo)
            matrix = EpistemicallyBoundedMatrixBuilder(ledger).build([snapshot.observation_id])
            counts_before = [len(ledger.rows(table)) for table in ("observations", "attempts", "decisions")]

            result = subprocess.run(
                [sys.executable, str(ROOT / "tools" / "case_preview.py"), "--db", str(db), matrix.observation_id],
                cwd=ROOT, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Case preview", result.stdout)
            self.assertIn(matrix.observation_id, result.stdout)
            self.assertIn(snapshot.observation_id, result.stdout)
            self.assertIn("UNKNOWN", result.stdout)
            self.assertIn("pre_intake", result.stdout)
            self.assertIn("No target", result.stdout)
            self.assertEqual(counts_before, [len(ledger.rows(table)) for table in ("observations", "attempts", "decisions")])

    def test_wrong_observation_fails_without_creating_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "ledger.db"
            ledger = EvidenceLedger(db)
            ledger.initialize()
            source = ledger.record_observation("repo.record", "test", {"name": "x"})
            result = subprocess.run(
                [sys.executable, str(ROOT / "tools" / "case_preview.py"), "--db", str(db), source.evidence_id],
                cwd=ROOT, capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not a Processor matrix", result.stderr)
            self.assertEqual(len(ledger.rows("observations")), 1)

    def test_malformed_unknown_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "ledger.db"
            ledger = EvidenceLedger(db)
            ledger.initialize()
            source = ledger.record_observation("processor.feature_matrix", "test", {
                "repo_record_ids": ["repo:test"], "feature_names": ["mechanisms"],
                "values": [[[]]], "missingness": [[True]],
                "evidence_scope": "pre_intake", "completeness": "partial", "source_snapshot_ids": ["source"],
            })
            result = subprocess.run(
                [sys.executable, str(ROOT / "tools" / "case_preview.py"), "--db", str(db), source.evidence_id],
                cwd=ROOT, capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("UNKNOWN", result.stderr)


if __name__ == "__main__":
    unittest.main()
