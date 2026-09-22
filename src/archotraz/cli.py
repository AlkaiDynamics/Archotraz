from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
from typing import Sequence

from .bopo import BopoConfigurationError, BopoHttpControlPort
from .cells import CellHousing, CellPlacement
from .config import ArchotrazConfig
from .evidence import EvidenceLedger
from .guards import PairEnumerationGuard
from .processor import EpistemicallyBoundedProcessor
from .repositories import ManualRepositoryIngestor
from .warden import Warden


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="archotraz")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="initialize the canonical SQLite Evidence Ledger")
    init.add_argument("--db", type=Path, help="override the SQLite ledger path")

    ingest = sub.add_parser("ingest-repo", help="manually ingest a repository into the evidence ledger")
    ingest.add_argument("url", help="repository URL")
    ingest.add_argument("--db", type=Path, help="override the SQLite ledger path")
    ingest.add_argument("--priority", help="optional user-supplied priority")
    ingest.add_argument("--tag", action="append", default=[], help="optional tag; may be repeated")
    ingest.add_argument("--desired-block", help="optional user-supplied cell-block preference")
    ingest.add_argument(
        "--algorithm-override",
        action="append",
        default=[],
        help="optional algorithm override; may be repeated",
    )
    ingest.add_argument(
        "--guard-override",
        action="append",
        default=[],
        help="optional guard override; may be repeated",
    )
    ingest.add_argument("--notes", help="optional manual notes")
    ingest.add_argument("--provenance-ref", help="optional provenance reference for the manual entry")

    place_cell = sub.add_parser("place-cell", help="record an explicit initial Cell Housing placement")
    place_cell.add_argument("repo_record_id", help="canonical RepoRecord id")
    place_cell.add_argument("--db", type=Path, help="override the SQLite ledger path")
    place_cell.add_argument("--block", required=True, choices=["A", "B", "C", "GEN-POP", "AD-SEG"])
    place_cell.add_argument("--cell", required=True, dest="cell_id", help="cell identifier")
    place_cell.add_argument("--rationale", required=True, help="explicit placement rationale")

    cell_current = sub.add_parser("cell-current", help="show the current Cell Housing placement")
    cell_current.add_argument("repo_record_id", help="canonical RepoRecord id")
    cell_current.add_argument("--db", type=Path, help="override the SQLite ledger path")

    cell_history = sub.add_parser("cell-history", help="show immutable Cell Housing placement history")
    cell_history.add_argument("repo_record_id", help="canonical RepoRecord id")
    cell_history.add_argument("--db", type=Path, help="override the SQLite ledger path")

    guard_pairs = sub.add_parser(
        "guard-pairs",
        help="enumerate the complete unordered pair universe for explicitly placed repositories",
    )
    guard_pairs.add_argument("repo_record_ids", nargs="+", help="canonical RepoRecord ids")
    guard_pairs.add_argument("--db", type=Path, help="override the SQLite ledger path")

    process_features = sub.add_parser(
        "process-features",
        help="normalize existing RepoRecord/Detective evidence into an explicit partial feature snapshot",
    )
    process_features.add_argument("repo_record_id", help="canonical RepoRecord id")
    process_features.add_argument("--db", type=Path, help="override the SQLite ledger path")

    doctor = sub.add_parser("doctor", help="check the Bopo control boundary and record results in SQLite")
    doctor.add_argument("--db", type=Path, help="override the SQLite ledger path")
    doctor.add_argument("--bopo-url", help="override the Bopo API base URL")
    doctor.add_argument("--company-id", help="Bopo company id; enables runtime preflight")
    doctor.add_argument("--provider", default="shell", help="Bopo provider type for preflight (default: shell)")
    doctor.add_argument("--skip-preflight", action="store_true", help="perform health only")

    return parser


def _config_from_args(args: argparse.Namespace) -> ArchotrazConfig:
    base = ArchotrazConfig.from_env()
    return ArchotrazConfig(
        db_path=args.db or base.db_path,
        dry_mode=base.dry_mode,
        bopo_base_url=(getattr(args, "bopo_url", None) or base.bopo_base_url).rstrip("/"),
        bopo_company_id=getattr(args, "company_id", None) or base.bopo_company_id,
        bopo_timeout_seconds=base.bopo_timeout_seconds,
    )


def _placement_payload(placement: CellPlacement | None) -> dict[str, object] | None:
    if placement is None:
        return None
    return {
        "repo_record_id": placement.repo_record_id,
        "block": placement.block.value,
        "cell_id": placement.cell_id,
        "stage": placement.stage,
        "eligibility": placement.eligibility,
        "version": placement.version,
        "rationale": placement.rationale,
        "evidence_basis": list(placement.evidence_basis),
        "decision_id": placement.decision_id,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = _config_from_args(args)
    ledger = EvidenceLedger(config.db_path)
    ledger.initialize()

    if args.command == "init":
        print(json.dumps({"ok": True, "ledger": str(config.db_path), "dry_mode": config.dry_mode}))
        return 0

    if args.command == "ingest-repo":
        ingestor = ManualRepositoryIngestor(ledger, dry_mode=config.dry_mode)
        result = ingestor.ingest(
            args.url,
            priority=args.priority,
            tags=tuple(args.tag),
            desired_block=args.desired_block,
            algorithm_overrides=tuple(args.algorithm_override),
            guard_overrides=tuple(args.guard_override),
            notes=args.notes,
            provenance_ref=args.provenance_ref,
        )
        print(
            json.dumps(
                {
                    "ok": True,
                    "created": result.created,
                    "record": result.record.to_payload(),
                    "record_evidence_id": result.record_evidence_id,
                    "ingested_evidence_id": result.ingested_evidence_id,
                    "detective_evidence_id": result.detective_evidence_id,
                },
                indent=2,
                sort_keys=True,
                default=str,
            )
        )
        return 0

    if args.command == "place-cell":
        placement = CellHousing(ledger).place(
            args.repo_record_id,
            block=args.block,
            cell_id=args.cell_id,
            rationale=args.rationale,
        )
        print(json.dumps({"ok": True, "placement": _placement_payload(placement)}, indent=2, sort_keys=True))
        return 0

    if args.command == "cell-current":
        placement = CellHousing(ledger).current(args.repo_record_id)
        print(json.dumps({"ok": True, "placement": _placement_payload(placement)}, indent=2, sort_keys=True))
        return 0

    if args.command == "cell-history":
        history = CellHousing(ledger).history(args.repo_record_id)
        print(
            json.dumps(
                {"ok": True, "history": [_placement_payload(placement) for placement in history]},
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    if args.command == "guard-pairs":
        result = PairEnumerationGuard(ledger).run(args.repo_record_ids)
        print(
            json.dumps(
                {
                    "ok": True,
                    "guard": result.contract.name,
                    "candidate_count": result.candidate_count,
                    "pair_count": result.pair_count,
                    "complete_unordered_universe": result.complete_unordered_universe,
                    "attempt_id": result.attempt_id,
                    "pairs": [asdict(pair) for pair in result.pairs],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    if args.command == "process-features":
        snapshot = EpistemicallyBoundedProcessor(ledger).extract(args.repo_record_id)
        payload = snapshot.to_payload()
        payload.update({"ok": True, "processor": EpistemicallyBoundedProcessor.name})
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return 0

    if args.command == "doctor":
        port = BopoHttpControlPort(
            base_url=config.bopo_base_url,
            company_id=config.bopo_company_id,
            timeout_seconds=config.bopo_timeout_seconds,
        )
        warden = Warden(ledger=ledger, bopo=port, dry_mode=config.dry_mode)
        health = warden.check_bopo_health()
        result: dict[str, object] = {
            "ok": 200 <= health.status_code < 300,
            "dry_mode": config.dry_mode,
            "ledger": str(config.db_path),
            "health": health.payload,
            "health_request_id": health.request_id,
        }
        if not args.skip_preflight:
            if not config.bopo_company_id:
                raise BopoConfigurationError(
                    "doctor preflight requires --company-id or ARCHOTRAZ_BOPO_COMPANY_ID; "
                    "use --skip-preflight for health-only checks"
                )
            preflight = warden.check_bopo_preflight(args.provider)
            result["preflight"] = preflight.payload
            result["preflight_request_id"] = preflight.request_id
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
        return 0 if bool(result["ok"]) else 1

    raise AssertionError(f"unhandled command: {args.command}")
