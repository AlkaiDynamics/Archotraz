from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from archotraz.evidence import EvidenceLedger
from archotraz.repositories import ManualRepositoryIngestor


class CellHousingContractTests(unittest.TestCase):
    def test_cells_module_exists(self) -> None:
        self.assertIsNotNone(importlib.util.find_spec("archotraz.cells"))

    def test_evidence_ledger_exposes_decision_recording(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = EvidenceLedger(Path(tmp) / "ledger.db")
            ledger.initialize()
            self.assertTrue(hasattr(ledger, "record_decision"))


if __name__ == "__main__":
    unittest.main()
