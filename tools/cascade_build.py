#!/usr/bin/env python3
"""Run verified Archotraz build stages; stop at missing implementations.

The optional recipe is a JSON object with a ``stages`` array. Each stage has an
``id``, ``requires`` (list of stage IDs), ``files`` (required repository paths),
``build`` (list of argv arrays), ``checks`` (list of argv arrays), and ``gate``.
Build commands require ``idempotent_build: true``. No command uses a shell.
This is developer build state, not canonical Archotraz evidence.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STAGES: list[dict[str, Any]] = [
    {
        "id": "verified_foundation",
        "requires": [],
        "files": ["src/archotraz/evidence.py", "src/archotraz/processor_matrix.py"],
        "build": [],
        "checks": [["{python}", "-m", "unittest", "discover", "-s", "tests", "-q"]],
        "gate": "Current merged foundation; this check does not certify future stages or Windows.",
    },
    {"id": "operator_case_slice", "requires": ["verified_foundation"], "files": [], "build": [], "checks": [],
     "gate": "Case view, Matrix Capability Card, and cold-start walkthrough; implement independently."},
    {"id": "identity_and_lineage", "requires": ["verified_foundation"], "files": [], "build": [], "checks": [],
     "gate": "Versioned source, mechanism, target, lineage, migrations, and transaction contracts."},
    {"id": "evidence_acquisition", "requires": ["identity_and_lineage"], "files": [], "build": [], "checks": [],
     "gate": "Adjudicator and bounded Intake with source and tool provenance."},
    {"id": "composition", "requires": ["evidence_acquisition"], "files": [], "build": [], "checks": [],
     "gate": "Candidate universe, directed edges, configurations, and bounded search."},
    {"id": "kitchen", "requires": ["composition"], "files": [], "build": [], "checks": [],
     "gate": "Named benchmarks, baselines, protected evaluation, and falsification."},
    {"id": "execution", "requires": ["kitchen"], "files": [], "build": [], "checks": [],
     "gate": "Sandbox, capability policy, retries, and crash recovery before untrusted execution."},
    {"id": "rehab", "requires": ["execution"], "files": [], "build": [], "checks": [],
     "gate": "Measured outcomes, failure attribution, invalidation, and policy bakeoffs."},
]


def load_stages(recipe: Path | None) -> list[dict[str, Any]]:
    data = {"stages": DEFAULT_STAGES} if recipe is None else json.loads(recipe.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("stages"), list):
        raise ValueError("recipe must contain a stages array")
    stages = data["stages"]
    seen: set[str] = set()
    for stage in stages:
        if not isinstance(stage, dict) or not isinstance(stage.get("id"), str) or not stage["id"]:
            raise ValueError("every stage needs a nonempty id")
        if stage["id"] in seen:
            raise ValueError(f"duplicate stage: {stage['id']}")
        for field in ("requires", "files", "build", "checks"):
            if not isinstance(stage.get(field), list):
                raise ValueError(f"{stage['id']}: {field} must be an array")
        if any(not isinstance(dep, str) or dep not in seen for dep in stage["requires"]):
            raise ValueError(f"{stage['id']}: dependencies must precede their stage")
        for name in stage["files"]:
            if not isinstance(name, str) or not name or Path(name).is_absolute() or ".." in Path(name).parts:
                raise ValueError(f"{stage['id']}: files must be repository-relative")
        for command in stage["build"] + stage["checks"]:
            if not isinstance(command, list) or not command or any(not isinstance(arg, str) for arg in command):
                raise ValueError(f"{stage['id']}: commands must be nonempty argv arrays")
        if stage["build"] and stage.get("idempotent_build") is not True:
            raise ValueError(f"{stage['id']}: build commands require idempotent_build: true")
        seen.add(stage["id"])
    return stages


def stage_key(stage: dict[str, Any], commit: str) -> str:
    raw = json.dumps({"stage": stage, "commit": commit}, sort_keys=True).encode()
    return hashlib.sha256(raw).hexdigest()


def git_commit() -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def read_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"receipts": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("receipts"), dict):
        raise ValueError("invalid cascade state")
    return data


def save_state(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def ready(stage: dict[str, Any]) -> bool:
    return bool(stage["files"] and stage["checks"] and all((ROOT / path).is_file() for path in stage["files"]))


def run(stages: list[dict[str, Any]], state_path: Path, through: str | None, only: str | None) -> int:
    ids = [stage["id"] for stage in stages]
    if through is not None and through not in ids:
        raise ValueError(f"unknown stage: {through}")
    if only is not None and only not in ids:
        raise ValueError(f"unknown stage: {only}")
    if only is not None and through is not None:
        raise ValueError("--only and --through cannot be used together")
    if only is not None:
        selected: set[str] = set()

        def include(name: str) -> None:
            selected.add(name)
            for dep in stages[ids.index(name)]["requires"]:
                include(dep)

        include(only)
        stages_to_run = [stage for stage in stages if stage["id"] in selected]
    else:
        stages_to_run = stages
    state = read_state(state_path)
    commit = git_commit()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    for stage in stages_to_run:
        name = stage["id"]
        if not ready(stage):
            print(f"BLOCKED {name}: {stage.get('gate', 'implementation and checks required')}")
            return 2
        key = stage_key(stage, commit)
        if any(state["receipts"].get(dep, {}).get("key") != stage_key(stages[ids.index(dep)], commit)
               or state["receipts"][dep].get("status") != "passed" for dep in stage["requires"]):
            print(f"BLOCKED {name}: dependency lacks a valid receipt")
            return 2
        if state["receipts"].get(name, {}).get("key") == key and state["receipts"][name].get("status") == "passed":
            print(f"REUSED {name} ({commit[:12]})")
        else:
            receipt = {"key": key, "commit": commit, "status": "running",
                       "started_at": datetime.now(timezone.utc).isoformat(), "commands": []}
            state["receipts"][name] = receipt
            save_state(state_path, state)
            for command in stage["build"] + stage["checks"]:
                argv = [sys.executable if arg == "{python}" else arg for arg in command]
                print(f"RUN {name}: {json.dumps(argv)}", flush=True)
                try:
                    result = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True, text=True)
                    receipt["commands"].append({"argv": argv, "returncode": result.returncode,
                                                 "stdout": result.stdout[-4000:], "stderr": result.stderr[-4000:]})
                    if result.returncode:
                        receipt["status"] = "failed"
                        save_state(state_path, state)
                        print(f"FAILED {name}: {result.stderr[-1200:] or result.stdout[-1200:]}")
                        return 1
                except OSError as exc:
                    receipt["status"] = "failed"
                    receipt["error"] = str(exc)
                    save_state(state_path, state)
                    print(f"FAILED {name}: {exc}")
                    return 1
            receipt["status"] = "passed"
            receipt["finished_at"] = datetime.now(timezone.utc).isoformat()
            save_state(state_path, state)
            print(f"PASSED {name} ({commit[:12]})")
        if name == through:
            return 0
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["plan", "status", "run"])
    parser.add_argument("--recipe", type=Path, help="JSON stage recipe; default shows the bounded Archotraz roadmap")
    parser.add_argument("--state", type=Path, default=ROOT / ".archotraz" / "cascade-state.json")
    parser.add_argument("--through", help="stop after this stage succeeds")
    parser.add_argument("--only", help="run this stage and its dependencies, allowing independent tracks")
    args = parser.parse_args(argv)
    try:
        stages = load_stages(args.recipe)
        if args.action == "run":
            return run(stages, args.state, args.through, args.only)
        receipts = read_state(args.state)["receipts"] if args.action == "status" else {}
        commit = git_commit()
        for stage in stages:
            receipt = receipts.get(stage["id"], {})
            valid = receipt.get("key") == stage_key(stage, commit) and receipt.get("status") == "passed"
            status = "verified" if valid else "ready" if ready(stage) else "blocked"
            print(f"{status:8} {stage['id']:24} {stage.get('gate', '')}")
        return 0
    except (ValueError, OSError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        print(f"cascade: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
