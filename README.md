# Archotraz

**The Archonic Jail:** An **algorithm orchestration framework** that rounds up useful repository mechanisms and unites them into a collaborative engine for forging high-value software. There is no escape!

Architecturally, Archotraz is a **stateful algorithmic search, routing, recombination, falsification, construction, and optimization machine**. It searches across repositories, tools, mechanisms, algorithms, guards, objectives, adapters, and prior experimental evidence to discover stronger software configurations.

It does not treat a repository as the permanent unit of intelligence. Repositories contribute evidence and mechanisms; configurations and measured system state become first-class experimental objects.

Its core loop is:

```text
REPRESENT → SEARCH → MATCH → GROUP → FALSIFY → BUILD → MEASURE → LEARN → RECOMBINE
```

Current MVP direction is deliberately narrow: manual repository intake, evidence-grounded profiling, cell state, pair/configuration search, Guard proposals, and inspectable Kitchen candidates before broader automation.

See [docs/architecture/ARCHITECTURE_CONTRACT.md](docs/architecture/ARCHITECTURE_CONTRACT.md) for the frozen implementation baseline.

## Bootstrap runtime

The current executable baseline is **Python 3.12+ as a modular monolith** with no runtime dependencies beyond the Python standard library.

```bash
python -m pip install -e . --no-build-isolation
archotraz init
```

The default canonical ledger is `.archotraz/archotraz.db`. **Dry Mode is on by default.**

With Bopo running on its default local API port:

```bash
archotraz doctor --skip-preflight
archotraz doctor --company-id <bopo-company-id> --provider shell
```

Bopo health and preflight results are recorded as external attempts/observations with provenance in the Archotraz SQLite ledger.

See [ADR-0001](docs/architecture/ADR-0001-python-modular-monolith.md) for the implementation-language decision and [the Bopo binding](docs/integrations/BOPO_BINDING.md) for the runtime boundary.
