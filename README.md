# Archotraz

**The Archonic Jail**

Archotraz is a stateful algorithmic search, routing, recombination, falsification, construction, and optimization machine for discovering stronger software configurations from repositories, tools, mechanisms, algorithms, guards, objectives, adapters, and prior experimental evidence.

It does not treat a repository as the permanent unit of intelligence. Repositories contribute evidence and mechanisms; configurations and measured system state become first-class experimental objects.

Its core loop is:

```text
REPRESENT → SEARCH → MATCH → GROUP → FALSIFY → BUILD → MEASURE → LEARN → RECOMBINE
```

Current MVP direction is deliberately narrow: manual repository intake, evidence-grounded profiling, cell state, pair/configuration search, Guard proposals, and inspectable Kitchen candidates before broader automation.

See [docs/architecture/ARCHITECTURE_CONTRACT.md](docs/architecture/ARCHITECTURE_CONTRACT.md) for the frozen implementation baseline.
