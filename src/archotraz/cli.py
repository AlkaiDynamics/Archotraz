from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .bopo import BopoConfigurationError, BopoHttpControlPort
from .cells import CellBlock, CellHousing
from .config import ArchotrazConfig
from .detective import Detective, GitHubPublicMetadataSource
from .evidence import EvidenceLedger
from .guards import PairCandidate, PairEligibilityGuard, PairUniverse
from .primitives import PrimitiveEvidenceStore, RawPairProjector
from .processor import Processor
from .repos import RepoRegistry
from .warden import Warden


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="archotraz")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="initialize the canonical SQLite Evidence Ledger")
    init.add_argument("--db", type=Path, help="override the SQLite ledger path")

    doctor = sub.add_parser("doctor", help="check the Bopo control boundary and record results in SQLite")
    doctor.add_argument("--db", type=Path, help="override the SQLite ledger path")
    doctor.add_argument("--bopo-url", help="override the Bopo API base URL")
    doctor.add_argument("--company-id", help="Bopo company id; enables runtime preflight")
    doctor.add_argument("--provider", default="shell", help="Bopo provider type for preflight (default: shell)")
    doctor.add_argument("--skip-preflight", action="store_true", help="perform health only")

    repo = sub.add_parser("repo", help="manual repository intake")
    repo_sub = repo.add_subparsers(dest="repo_command", required=True)
    repo_add = repo_sub.add_parser("add", help="create or reuse a canonical RepoRecord")
    repo_add.add_argument("url", help="GitHub repository URL")
    repo_add.add_argument("--db", type=Path, help="override the SQLite ledger path")
    repo_add.add_argument("--priority", type=int, help="optional user-supplied priority")
    repo_add.add_argument("--tag", action="append", default=[], help="repeatable user tag")
    repo_add.add_argument("--note", help="optional intake note")

    detective = sub.add_parser("detective", help="run cheap metadata triage for an existing RepoRecord")
    detective.add_argument("repo_id", help="RepoRecord id")
    detective.add_argument("--db", type=Path, help="override the SQLite ledger path")
    detective.add_argument("--timeout", type=float, default=10.0, help="metadata request timeout in seconds")

    profile = sub.add_parser("profile", help="build a deterministic profile from recorded evidence")
    profile.add_argument("repo_id", help="RepoRecord id")
    profile.add_argument("--db", type=Path, help="override the SQLite ledger path")

    cell = sub.add_parser("cell", help="inspect or explicitly assign reversible Cell state")
    cell_sub = cell.add_subparsers(dest="cell_command", required=True)

    cell_assign = cell_sub.add_parser("assign", help="explicitly assign a repository to a Cell block")
    cell_assign.add_argument("repo_id", help="RepoRecord id")
    cell_assign.add_argument("--block", required=True, choices=[block.value for block in CellBlock])
    cell_assign.add_argument("--reason", required=True, help="human/policy rationale for this assignment")
    cell_assign.add_argument("--cell", dest="cell_label", help="optional cell label within the block")
    cell_assign.add_argument("--policy-ref", help="optional policy/version reference")
    cell_assign.add_argument("--db", type=Path, help="override the SQLite ledger path")

    cell_show = cell_sub.add_parser("show", help="show current Cell assignment and assignment history")
    cell_show.add_argument("repo_id", help="RepoRecord id")
    cell_show.add_argument("--db", type=Path, help="override the SQLite ledger path")

    pairs = sub.add_parser("pairs", help="enumerate the complete unordered RepoRecord pair universe")
    pairs.add_argument("--db", type=Path, help="override the SQLite ledger path")

    guard = sub.add_parser("guard", help="run a production-authorized Guard")
    guard_sub = guard.add_subparsers(dest="guard_command", required=True)
    pair_eligibility = guard_sub.add_parser(
        "pair-eligibility",
        help="check distinct identity and explicit Cell readiness without claiming compatibility",
    )
    pair_eligibility.add_argument("repo_a_id", help="first RepoRecord id")
    pair_eligibility.add_argument("repo_b_id", help="second RepoRecord id")
    pair_eligibility.add_argument("--db", type=Path, help="override the SQLite ledger path")

    primitives = sub.add_parser("primitives", help="record raw evidence-backed matching primitives")
    primitives_sub = primitives.add_subparsers(dest="primitives_command", required=True)
    primitives_record = primitives_sub.add_parser("record", help="record one raw primitive observation")
    primitives_record.add_argument("repo_id", help="RepoRecord id")
    primitives_record.add_argument("--mechanism", action="append")
    primitives_record.add_argument("--target", action="append")
    primitives_record.add_argument("--have", action="append")
    primitives_record.add_argument("--need", action="append")
    primitives_record.add_argument("--data-model", action="append")
    primitives_record.add_argument("--access-pattern", action="append")
    primitives_record.add_argument("--fidelity", type=float)
    primitives_record.add_argument("--debt", type=float)
    primitives_record.add_argument("--source-ref", required=True, help="provenance reference for this observation")
    primitives_record.add_argument("--db", type=Path, help="override the SQLite ledger path")

    pair_features = sub.add_parser("pair-features", help="project raw pair relationships without a score")
    pair_features.add_argument("repo_a_id", help="first RepoRecord id")
    pair_features.add_argument("repo_b_id", help="second RepoRecord id")
    pair_features.add_argument("--db", type=Path, help="override the SQLite ledger path")

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


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = _config_from_args(args)
    ledger = EvidenceLedger(config.db_path)
    ledger.initialize()

    if args.command == "init":
        print(json.dumps({"ok": True, "ledger": str(config.db_path), "dry_mode": config.dry_mode}))
        return 0

    if args.command == "repo":
        registry = RepoRegistry(ledger)
        if args.repo_command == "add":
            result = registry.add_manual(
                args.url,
                priority=args.priority,
                tags=tuple(args.tag),
                notes=args.note,
            )
            print(json.dumps({"created": result.created, "repo": result.record.to_dict()}, indent=2, sort_keys=True))
            return 0
        raise AssertionError(f"unhandled repo command: {args.repo_command}")

    if args.command == "detective":
        registry = RepoRegistry(ledger)
        source = GitHubPublicMetadataSource(timeout_seconds=args.timeout)
        result = Detective(ledger=ledger, registry=registry, source=source).triage(args.repo_id)
        print(json.dumps({"ok": True, "source": result.source_type, "result": result.payload}, indent=2, sort_keys=True))
        return 0

    if args.command == "profile":
        registry = RepoRegistry(ledger)
        profile = Processor(ledger=ledger, registry=registry).profile(args.repo_id)
        print(json.dumps(profile.to_dict(), indent=2, sort_keys=True))
        return 0

    if args.command == "cell":
        registry = RepoRegistry(ledger)
        housing = CellHousing(ledger=ledger, registry=registry)
        if args.cell_command == "assign":
            assignment = housing.assign(
                args.repo_id,
                CellBlock(args.block),
                source="manual",
                reason=args.reason,
                cell_label=args.cell_label,
                policy_ref=args.policy_ref,
            )
            print(json.dumps(assignment.to_dict(), indent=2, sort_keys=True))
            return 0
        if args.cell_command == "show":
            current = housing.current(args.repo_id)
            history = housing.history(args.repo_id)
            print(
                json.dumps(
                    {
                        "repo_id": args.repo_id,
                        "current": None if current is None else current.to_dict(),
                        "history": [item.to_dict() for item in history],
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        raise AssertionError(f"unhandled cell command: {args.cell_command}")

    if args.command == "pairs":
        registry = RepoRegistry(ledger)
        pairs = PairUniverse(registry).enumerate()
        print(
            json.dumps(
                {
                    "count": len(pairs),
                    "pairs": [pair.to_dict() for pair in pairs],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    if args.command == "guard":
        registry = RepoRegistry(ledger)
        housing = CellHousing(ledger=ledger, registry=registry)
        if args.guard_command == "pair-eligibility":
            guard = PairEligibilityGuard(registry=registry, housing=housing)
            result = guard.evaluate_ids(args.repo_a_id, args.repo_b_id)
            print(
                json.dumps(
                    {
                        "contract": guard.contract.to_dict(),
                        "result": result.to_dict(),
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        raise AssertionError(f"unhandled guard command: {args.guard_command}")

    if args.command == "primitives":
        registry = RepoRegistry(ledger)
        store = PrimitiveEvidenceStore(ledger=ledger, registry=registry)
        if args.primitives_command == "record":
            evidence = store.record(
                args.repo_id,
                mechanisms=None if args.mechanism is None else tuple(args.mechanism),
                targets=None if args.target is None else tuple(args.target),
                have=None if args.have is None else tuple(args.have),
                need=None if args.need is None else tuple(args.need),
                data_models=None if args.data_model is None else tuple(args.data_model),
                access_patterns=None if args.access_pattern is None else tuple(args.access_pattern),
                fidelity=args.fidelity,
                debt=args.debt,
                source="manual",
                source_ref=args.source_ref,
            )
            profile = store.latest(args.repo_id)
            print(
                json.dumps(
                    {"evidence_id": evidence.evidence_id, "profile": profile.to_dict()},
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        raise AssertionError(f"unhandled primitives command: {args.primitives_command}")

    if args.command == "pair-features":
        registry = RepoRegistry(ledger)
        store = PrimitiveEvidenceStore(ledger=ledger, registry=registry)
        registry.get(args.repo_a_id)
        registry.get(args.repo_b_id)
        features = RawPairProjector(store).project(PairCandidate(args.repo_a_id, args.repo_b_id))
        print(json.dumps(features.to_dict(), indent=2, sort_keys=True))
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
