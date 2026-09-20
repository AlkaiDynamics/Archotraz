# Bopo Runtime Binding

Status: **BOUND FOR MVP RUNTIME INTEGRATION**

This document resolves the previously-unbound Bopo repository identity and defines the narrow integration boundary Archotraz is allowed to use.

## 1. Authority split

### CONFIRMED — recovered project decision

The authoritative keeper corpus selected:

```text
bopodev/bopo
https://github.com/bopodev/bopo
```

The later Archotraz stack lock assigns Bopo the role:

```text
local runtime/control shell
→ contracts
→ bus
→ runtime
```

Taskade-style normalization remains a later optional extension.

### VERIFIED CURRENT — external repository state

Verified against `bopodev/bopo` current `main` during the Archotraz bootstrap:

- workspace version: `0.1.38`;
- published CLI package: `bopodev`, version `0.1.38`;
- CLI binaries: `bopodev` and `bopo`;
- verified current `main` commit used for the initial binding: `d9d105353837930966aacc635d1df8364ecb4035`;
- license: MIT;
- runtime prerequisites: Node.js 20+, pnpm 9+;
- default local web UI: `http://localhost:4010`;
- default local API: `http://localhost:4020`;
- API style: JSON HTTP routes with no `/api` prefix;
- runtime model: provider-agnostic adapters behind an API/control plane;
- local-first/self-hosted operation.

These are implementation facts, not recovered historical decisions. They must be re-verified before a future version bump.

## 2. Binding decision

Archotraz binds Bopo as an **external runtime/control-plane dependency**, not as its epistemic core.

The boundary is:

```text
ARCHOTRAZ
  ├─ Warden policy
  ├─ SQLite Evidence Ledger          ← canonical truth
  ├─ stages / Guards / Kitchen
  └─ Bopo Control Port
        ↓
     Bopo API / CLI
        ↓
     runtime adapters / shell / HTTP / agent execution
```

Bopo may execute, schedule, expose runtime health, and report run outcomes.

Bopo may **not** become the authoritative store for:
- Archotraz observations;
- claims;
- failures;
- attempts;
- decisions;
- supersessions;
- contradictions;
- provenance;
- cell state;
- Guard authority;
- Kitchen decisions.

Those remain under Archotraz and its SQLite Evidence Ledger.

## 3. Why the boundary is narrow

Bopo includes its own company, project, issue, agent, governance, memory, scheduler, and database models.

Archotraz must not silently inherit those models merely because Bopo provides them.

The two systems have different authority domains:

```text
Bopo
= runtime/control execution state

Archotraz
= evidence-backed search, routing, falsification, configuration state
```

Bopo's internal persistence is therefore operational state, not Archotraz truth.

## 4. Initial allowed integration surface

The first integration should prefer explicit API/CLI contracts rather than importing Bopo internals.

### Health / preflight

Allowed:

```text
GET /health
bopodev doctor
```

Purpose:
- verify the Bopo service is reachable;
- verify database/runtime command readiness;
- surface runtime availability to Warden.

### Correlation

Use `x-request-id` when calling the Bopo API so Archotraz can retain a correlation identifier in its own attempt/provenance records.

A Bopo request id is a foreign execution reference, not an Archotraz evidence id.

### Runtime execution doors

When an Archotraz stage is authorized to cross an execution door, Bopo runtime surfaces may be used for bounded execution.

Relevant Bopo capabilities include:
- shell runtime;
- generic HTTP runtime;
- adapter-backed runtimes;
- heartbeat execution;
- stop/resume/redo;
- observability of runs/messages/artifacts.

The exact Archotraz execution-door mapping is still subject to Dry Mode and stage authorization.

### Observability

Archotraz may read Bopo run/trace/cost/artifact output as **external observations**.

Before such data acquires Archotraz authority it must be copied into the SQLite Evidence Ledger with:
- source;
- retrieval/execution timestamp;
- Bopo request/run identifier;
- stage/worker identity;
- interpretation status;
- provenance.

## 5. Initially disallowed coupling

Do not:

- use Bopo's Postgres/embedded database as the Archotraz Evidence Ledger;
- write Archotraz stages directly against Bopo database tables;
- make Bopo issue state the canonical Archotraz pipeline state;
- make Bopo memory the canonical CodeMesh/evidence memory;
- expose Bopo agent conclusions directly as measurements;
- inherit Bopo's multi-company product model into the Archotraz domain model;
- let Bopo approval state replace Warden/Orbit/Kitchen gates;
- import Bopo's web UI as the Warden state model;
- bind Archotraz to provider-specific adapter internals.

## 6. Version pin

Initial development reference:

```text
repository: https://github.com/bopodev/bopo
commit:     d9d105353837930966aacc635d1df8364ecb4035
workspace:  0.1.38
CLI:        bopodev@0.1.38
```

The commit pin is the reproducibility anchor.

The semantic/package version is descriptive and useful for installation, but it does not replace the commit pin when exact source behavior matters.

## 7. Upgrade rule

A Bopo upgrade must not be treated as a transparent dependency bump.

Before changing the pin, re-verify at minimum:

1. `GET /health` behavior;
2. required actor/company headers;
3. runtime preflight behavior;
4. execution/run identifiers;
5. heartbeat/run lifecycle routes used by Archotraz;
6. observability response shapes used by Archotraz;
7. CLI command names used by local setup;
8. default ports or environment overrides;
9. license;
10. whether any Bopo change would alter Archotraz stage or evidence authority.

If a new Bopo version requires Archotraz to change canonical state ownership, stage ownership, or Dry Mode boundaries, that change requires an explicit Archotraz architecture decision rather than an ordinary dependency update.

## 8. Warden interface requirement

Archotraz implementation code should depend on an Archotraz-owned control interface, conceptually:

```text
BopoControlPort
  health()
  preflight()
  execute(authorized_execution_request)
  stop(external_run_id)
  resume(external_run_id)
  observe(external_run_id)
```

This is a boundary contract, not a language/API signature.

The implementation language and concrete class/module layout are intentionally not selected here.

Warden calls the port.
The Bopo adapter implements the port.
Archotraz domain logic does not call Bopo routes directly.

## 9. Acceptance condition for the scaffold

The first Bopo + Warden scaffold is acceptable when it can prove all of the following without implementing the full Archotraz pipeline:

```text
Archotraz starts
→ Warden loads
→ Bopo binding is configured
→ Bopo health/preflight can be checked
→ result is recorded as an external attempt/observation
→ canonical SQLite state remains authoritative
→ Dry Mode can prevent execution-door crossing
```

No agent autonomy is required to satisfy this checkpoint.
