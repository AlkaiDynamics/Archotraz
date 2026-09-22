#!/usr/bin/env python3
"""Read-only operator preview of one recorded Processor matrix; no Case persistence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import sys
from urllib.parse import quote


class PreviewError(ValueError):
    pass


def load_matrix(db: Path, observation_id: str) -> dict:
    if not db.is_file():
        raise PreviewError(f"ledger not found: {db}")
    uri = "file:" + quote(str(db.resolve()), safe="/") + "?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True) as conn:
            row = conn.execute("SELECT kind, payload_json FROM observations WHERE id = ?", (observation_id,)).fetchone()
    except sqlite3.DatabaseError as exc:
        raise PreviewError(f"cannot read ledger: {exc}") from exc
    if row is None:
        raise PreviewError(f"observation not found: {observation_id}")
    if row[0] != "processor.feature_matrix":
        raise PreviewError(f"not a Processor matrix: {observation_id}")
    try:
        payload = json.loads(row[1])
    except (TypeError, ValueError) as exc:
        raise PreviewError("matrix payload is malformed") from exc
    if not isinstance(payload, dict):
        raise PreviewError("matrix payload is malformed")
    return payload


def render(payload: dict, observation_id: str) -> str:
    ids = payload.get("repo_record_ids")
    columns = payload.get("feature_names")
    values = payload.get("values")
    mask = payload.get("missingness")
    sources = payload.get("source_snapshot_ids")
    if (not isinstance(ids, list) or not ids or not all(isinstance(x, str) for x in ids)
            or not isinstance(columns, list) or not columns or not all(isinstance(x, str) for x in columns)
            or len(set(columns)) != len(columns)
            or not isinstance(values, list) or not isinstance(mask, list)
            or not isinstance(sources, list) or len(sources) != len(ids)
            or not all(isinstance(x, str) for x in sources)
            or len(values) != len(ids) or len(mask) != len(ids)):
        raise PreviewError("matrix dimensions or source identities are malformed")
    counts = []
    for row, missing in zip(values, mask):
        if (not isinstance(row, list) or not isinstance(missing, list)
                or len(row) != len(columns) or len(missing) != len(columns)
                or any(type(flag) is not bool for flag in missing)):
            raise PreviewError("matrix row or missingness mask is malformed")
        for value, is_missing in zip(row, missing):
            if is_missing and value is not None:
                raise PreviewError("UNKNOWN must have value null and M=true")
            if not is_missing and value is None:
                raise PreviewError("known value cannot be null with M=false")
        counts.append(sum(missing))
    scope = payload.get("evidence_scope")
    completeness = payload.get("completeness")
    if not isinstance(scope, str) or not isinstance(completeness, str):
        raise PreviewError("matrix scope or completeness is malformed")

    def safe(value: str) -> str:
        return value.replace("|", "\\|").replace("\n", " ")

    lines = [
        "# Case preview — Processor matrix", "",
        "This is a read-only view of one matrix observation. No canonical Case has been created.", "",
        f"**Matrix observation:** `{safe(observation_id)}`  ",
        f"**Scope:** `{safe(scope)}`  ",
        f"**Completeness:** `{safe(completeness)}`", "",
        "## What is the goal?", "",
        "No target or workload is recorded in this matrix. Set a TargetSpec in a later Case slice.", "",
        "## What is known?", "",
        f"{len(ids)} candidate row(s); {len(columns)} typed feature column(s).", "",
        "| Repository | UNKNOWN fields | Source feature snapshot |", "| --- | ---: | --- |",
    ]
    for repo_id, unknown_count, source in zip(ids, counts, sources):
        lines.append(f"| `{safe(repo_id)}` | {unknown_count} | `{safe(source)}` |")
    lines.extend(["", "## What is unknown?", ""])
    for repo_id, missing in zip(ids, mask):
        unknown = ", ".join(safe(column) for column, absent in zip(columns, missing) if absent)
        lines.append(f"- `{safe(repo_id)}`: {unknown or 'No missing features in this matrix.'}")
    lines.extend([
        "", "## What has been tried?", "",
        "This view contains a typed matrix projection and its source IDs. It does not contain test or experiment outcomes.",
        "", "## What can I do next?", "",
        "- Inspect the recorded source feature snapshots by their observation IDs.",
        "- Record a target and acquire deeper evidence in later, separately verified slices.",
        "- Read `docs/capabilities/PROCESSOR_MATRIX.md` for an invocation and verification recipe.",
        "", "**Boundary:** UNKNOWN means `X=null, M=true`. This matrix does not score, rank, classify,",
        "recommend, test, or establish that any mechanism works.", "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("matrix_observation_id", help="exact processor.feature_matrix observation ID")
    parser.add_argument("--db", type=Path, required=True, help="existing canonical SQLite ledger")
    args = parser.parse_args()
    try:
        print(render(load_matrix(args.db, args.matrix_observation_id), args.matrix_observation_id))
        return 0
    except PreviewError as exc:
        print(f"case preview: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
