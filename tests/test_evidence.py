from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from archotraz.evidence import CANONICAL_TABLES, EvidenceLedger


class EvidenceLedgerTests(unittest.TestCase):
    def test_initialize_creates_all_canonical_tables(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = EvidenceLedger(Path(tmp) / "ledger.db")
            ledger.initialize()
            self.assertTrue(set(CANONICAL_TABLES).issubset(ledger.table_names()))
            meta = ledger.rows("schema_meta")
            self.assertEqual(meta, [{"key": "schema_version", "value": "1"}])

    def test_attempt_observation_and_provenance_are_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = EvidenceLedger(Path(tmp) / "ledger.db")
            ledger.initialize()
            attempt_id = ledger.begin_attempt("bopo.health", {"check": True})
            ledger.finish_attempt(attempt_id, status="succeeded", output={"ok": True}, request_id="req-1")
            observation = ledger.record_observation("bopo.health", "bopo", {"ok": True}, external_ref="req-1")
            ledger.record_provenance(observation, source_type="bopo", source_ref="req-1")

            self.assertEqual(ledger.rows("attempts")[0]["status"], "succeeded")
            self.assertEqual(ledger.rows("observations")[0]["external_ref"], "req-1")
            self.assertEqual(ledger.rows("provenance")[0]["evidence_id"], observation.evidence_id)


if __name__ == "__main__":
    unittest.main()
