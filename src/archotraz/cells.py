from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .evidence import EvidenceLedger


class CellBlock(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    GEN_POP = "GEN-POP"
    AD_SEG = "AD-SEG"


@dataclass(frozen=True, slots=True)
class CellPlacement:
    repo_record_id: str
    block: CellBlock
    cell_id: str
    stage: str
    eligibility: str
    version: int
    rationale: str
    evidence_basis: tuple[str, ...]
    decision_id: str


class CellHousing:
    def __init__(self, ledger: EvidenceLedger):
        self.ledger = ledger
