from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .bopo import BopoConfigurationError, BopoHttpControlPort
from .config import ArchotrazConfig
from .evidence import EvidenceLedger
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
