# ADR-0001 — Python 3.12 Modular Monolith

Status: **CONFIRMED**

## Decision

Archotraz MVP implementation uses **Python 3.12+ as a modular monolith**.

This decision was explicitly authorized after the architecture and Bopo binding checkpoints. It is an Archotraz implementation decision; it is not inherited from Bopo or another project.

## Initial module boundary

```text
archotraz.config     environment/configuration boundary
archotraz.evidence   canonical SQLite Evidence Ledger
archotraz.bopo       Bopo control-port adapter
archotraz.warden     policy/control boundary and Dry Mode gate
archotraz.cli        minimal local operator entry point
```

The module boundary is deliberately small. Stage/Guard/Kitchen modules are not created until their executable behavior is implemented.

## Runtime principles

1. **SQLite is canonical.** External Bopo state is operational evidence, not Archotraz truth.
2. **Stdlib first.** The first scaffold uses `sqlite3`, `urllib`, `argparse`, and `unittest`; no web framework or ORM is introduced.
3. **Bopo remains behind a port.** Domain logic must not call Bopo HTTP routes directly.
4. **Dry Mode defaults on.** Health, preflight, analysis, and evidence capture may continue; side-effecting execution doors fail closed.
5. **Unknowns remain explicit.** This ADR does not select the hostile-code sandbox, future UI stack, distributed execution model, or performance accelerators.

## Why Python here

The Archotraz core is dominated by algorithmic search, graph/statistical analysis, falsification, benchmarking, scientific computation, and SQLite-backed experimental state. Python provides the strongest path to those workloads without forcing the Bopo TypeScript implementation language across the system boundary.

## Revisit triggers

Reconsider the language boundary only when measured evidence shows a specific subsystem cannot meet its target budget. Candidate responses include native extensions or isolated Rust/C++ hot paths; they do not require rewriting the control/evidence core by default.
