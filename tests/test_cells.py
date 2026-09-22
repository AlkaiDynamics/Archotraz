from __future__ import annotations

import importlib
import importlib.util
import tempfile
import unittest
from pathlib import Path

from archotraz.evidence import EvidenceLedger


class CellHousingContractTests(unittest.TestCase):
    def test_cells_module_exists(self) -> None:
        self.assertIsNotNone(importlib.util.find_spec("archotraz.cells"))

    def test_cells_module_exposes_required_types(self) -> None:
        cells = importlib.import_module("archotraz.cells")
        self.assertTrue(hasattr(cells, "CellBlock"))
        self.assertTrue(hasattr(cells, "CellPlacement"))
        self.assertTrue(hasattr(cells, "CellHousing"))

    def test_evidence_ledger_exposes_decision_recording(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = EvidenceLedger(Path(tmp) / "ledger.db")
            ledger.initialize()
            self.assertTrue(hasattr(ledger, "record_decision"))


if __name__ == "__main__":
    unittest.main()
