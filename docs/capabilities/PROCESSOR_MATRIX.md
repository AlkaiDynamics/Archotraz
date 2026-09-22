# Processor Matrix — Capability Card

**Purpose:** project explicitly selected `processor.feature_snapshot` observations into a typed rectangular matrix with a separate missingness mask. It does not inspect source, encode numerically, score, rank, classify, or recommend.

## Invoke

From the repository root with Python 3.12+ and `PYTHONPATH=src` (or after installing the package):

```bash
PYTHONPATH=src python -m archotraz process-matrix SNAPSHOT_ID --db PATH_TO_LEDGER.db
```

`SNAPSHOT_ID` must be an existing `processor.feature_snapshot` observation ID, returned by `process-features`. More than one ID may be supplied. Use the `--db` path for the ledger containing those exact observations.

The command prints JSON. Copy its `observation_id` into the read-only Case preview:

```bash
python tools/case_preview.py MATRIX_OBSERVATION_ID --db PATH_TO_LEDGER.db
```

The preview prints Markdown to the terminal. It does not create a Case, alter the ledger, or export a file. Redirect its output to a file if you want to save a copy.

## Read the result

`repo_record_ids` identify matrix rows. `feature_names` identify columns. `values` holds typed, unencoded values; `missingness` has the same shape. **An unknown is `values[row][column] = null` and `missingness[row][column] = true`.** An empty list is not interchangeable with an unknown. `evidence_scope=pre_intake` and `completeness=partial` mean this is early evidence, not a full repository assessment.

`source_snapshot_ids` link rows to the exact input observations. The preview lists those IDs, unknown feature names, and the limits of this projection. There is no target, experiment, or recommendation in the matrix.

## Failure and recovery

- Snapshot ID missing or wrong kind: copy the `observation_id` from `process-features` and confirm `--db` is the same ledger.
- Mixed scopes, completeness, duplicate candidates, malformed values: `process-matrix` fails closed and records a failed attempt. Inspect the selected source snapshots and rerun with valid explicit IDs.
- Preview says matrix observation missing or wrong kind: supply the `observation_id` printed by `process-matrix`, not its attempt ID or input snapshot ID.
- Ledger unavailable: verify the `--db` path. The preview will not initialize a new ledger.

**Verified against:** the `tests/test_cli.py`, `tests/test_processor_matrix.py`, and `tests/test_case_preview.py` behaviors on this experimental branch. A complete operator Case and goal entry remain future work.
