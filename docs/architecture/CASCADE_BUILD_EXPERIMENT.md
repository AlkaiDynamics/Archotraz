# Cascade build experiment

This is a **developer build conductor**, not the Archotraz runtime or an agent that invents missing components. It is isolated on `experiment/cascade-build-driver`. It reads a sequence of stage definitions, checks existing work, records receipts, and refuses to advance through an unimplemented gate. It does not modify the canonical SQLite ledger or any existing Processor behavior.

## Use from the repository root

```bash
python tools/cascade_build.py plan
python tools/cascade_build.py run --through verified_foundation
python tools/cascade_build.py status
python tools/cascade_build.py run --only identity_and_lineage
```

The foundation gate runs the repository's unittest suite using `PYTHONPATH=src`. Its receipt is a local developer file at `.archotraz/cascade-state.json`. `--only` selects a stage and its prerequisites: independent Case and identity work can proceed in separate branches without requiring either to finish first. A branch does **not** turn its local receipt into evidence that another branch passed; verification must be repeated on the integrated commit. No merge or publish occurs here.

The remaining stages have neither implementations nor verification commands; the default recipe therefore stops at their gates. A future stage becomes runnable only when it names existing files and meaningful checks. To add a real build command, provide a JSON recipe with `stages` in dependency order; each stage has `id`, `requires`, `files`, `build`, `checks`, and `gate`. Commands are argv arrays, run without a shell. Nonempty `build` additionally requires `idempotent_build: true` because interrupted commands can be retried.

Receipts are keyed to the commit and stage definition. They record command return codes and abbreviated outputs. The script does not establish source identity for uncommitted edits; re-run checks after committing and before any promotion. Build receipts are operational verification, never observations or decisions in the canonical evidence ledger.

## Scope and limits

The default sequence covers foundation, operator Case, identity/lineage, evidence acquisition, composition, Kitchen, execution, and Rehab. It is an ordering and gate map, **not an implementation of those future stages**. Each needs its own bounded specification, code, and verified checks. The first trial is to see whether this conductor reduces repeated manual setup while preserving stop conditions and independent branches. If it cannot, retire the experiment rather than forcing the architecture into one script.
