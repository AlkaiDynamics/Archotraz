# Archotraz Polymorphic Transformation Architecture — Phase 2 Design

Status: **DRAFT FOR OPERATOR REVIEW**

Base: `main` at `a4bb3f17edc28b770d3dce9dac2af0f290a84223`

## Purpose

Archotraz must not be forced into a single architectural metaphor such as pipeline, compiler, search engine, experiment system, build system, or operator application. The same underlying state should support all of those interpretations when useful.

The design objective is therefore:

> Build one self-describing transformation substrate whose state can be viewed and executed as pipelines, compiler passes, search spaces, experiments, dependency graphs, executable plans, and operator cases without duplicating truth or inventing separate state models.

The implementation must also preserve the existing Archotraz epistemic laws:

- evidence is distinct from derived metrics, predictions, and decisions;
- UNKNOWN remains explicit;
- repository identity does not become permanent mechanism identity;
- scores do not become evidence;
- Bopo remains operational rather than canonical;
- SQLite remains canonical for Archotraz evidence/state until a later explicit architecture decision changes that;
- Dry Mode and later capability gates continue to fail closed;
- no architectural metaphor receives exclusive ownership of the system.

## Current boundary

The verified merged foundation already provides:

- canonical SQLite Evidence Ledger;
- Warden/Bopo control boundary;
- manual repository ingestion;
- Detective evidence;
- explicit Cell Housing state;
- first Matcher-family Guard;
- bounded Processor feature extraction with explicit missingness.

The active `feature/processor-feature-matrix` branch is a bounded projection experiment, not a corpus-scale matrix engine. Its current role is to prove deterministic `X/M` projection over explicit Processor snapshots while preserving UNKNOWN.

The bootstrap `Detective -> manual Cell -> Guard` route remains a plumbing/structural validation path, not an evidence-backed election path.

## Core design law

**One graph, many lenses.**

The same canonical objects, evidence, transformations, and receipts may be interpreted as:

- a stage pipeline when the operator asks what happens next;
- a compiler derivation when inspecting how a configuration was produced;
- a dependency graph when determining what must be reconsidered after a change;
- a search space when comparing alternatives;
- an experiment graph when falsifying a claim;
- an execution DAG when scheduling work;
- a case file when presenting human-operable state;
- a reusable memory graph when deciding what may be reused.

No lens may create an independent authority model.

## Minimal substrate

Phase 2 should converge on a small semantic substrate rather than a proliferation of independent subsystems.

### Entity

A versioned subject that can participate in evidence and transformations.

Representative entity kinds include:

- repository;
- repository snapshot;
- mechanism;
- target/workload;
- candidate universe;
- directed integration edge;
- configuration;
- benchmark;
- environment;
- artifact;
- case.

Entity kinds retain typed schemas, but share common identity/version/provenance infrastructure.

### Evidence

Evidence states what is known about an entity or relationship and why.

Minimum fields conceptually include:

- evidence ID;
- subject ID;
- property/assertion;
- epistemic state;
- value;
- source;
- `derived_from` lineage;
- method/tool/contract version;
- observation time.

The representation must eventually distinguish at least observed, declared, inferred, unknown, conflicted, stale, and superseded states. The first implementation may support a smaller subset provided evolution is versioned.

Lineage is computational: it must support selective invalidation and reprocessing, not merely human-readable provenance.

### Transformation

A bounded semantic operation over existing state.

Representative transformations include Detect, Parse, Normalize, ExtractMechanism, Match, BridgeSearch, Validate, Falsify, Build, Measure, Compare, and Explain.

Each transformation declares:

- input contract;
- output contract;
- semantic version;
- permissions/effects;
- cache identity inputs;
- stream/batch behavior;
- estimated or measured resource class;
- authority boundary;
- failure classes.

Existing Archotraz stages such as Detective, Processor, Guards, Kitchen, Rehab, and Work Release remain valid domain concepts, but they share transformation infrastructure instead of owning separate execution systems.

### Receipt/Event

Every transformation attempt emits a durable receipt/event describing what happened.

Minimum receipt fields conceptually include:

- transformation identity/version;
- exact inputs;
- status;
- outputs/artifacts;
- evidence created;
- wall time;
- CPU time where measurable;
- peak RAM where measurable;
- cache/reuse status;
- permissions/effects actually used;
- failure attribution;
- verification result.

Receipts provide the common substrate for resume, performance analysis, policy bakeoffs, debugging, verification, and operator progress.

## Archotraz IR

Archotraz should maintain a case-oriented intermediate representation rather than forcing each stage to invent a private model.

Conceptually:

```text
CaseIR
|- target/workload
|- entities
|- evidence
|- unknown holes
|- constraints
|- candidate universe
|- candidate configurations
|- transformation graph
|- resource constraints
|- lineage
|- current permissible actions
```

The IR is not necessarily one monolithic serialized object. It is a logical view over canonical state and rebuildable projections.

Transformations consume relevant portions of this IR and emit deltas rather than replacing global state.

## UNKNOWN as a resolvable hole

UNKNOWN is not only a value state. When an unknown blocks progress, Archotraz may represent it as a resolvable hole.

Example:

```text
Hole H17
required fact: interface_schema(Mechanism M42)
possible resolvers:
- inspect exported type
- static parser
- code graph
- sandboxed probe
- operator judgment
```

The scheduler's immediate question becomes:

> Which unresolved hole blocks a pending decision, and what is the cheapest permitted transformation likely to resolve it?

A scheduling estimate never becomes evidence that the underlying claim is true.

## Typed mechanism contracts and bridge search

Mechanisms should progressively expose typed contracts for inputs, outputs, constraints, effects, and uncertainties.

Compatibility becomes a composition question rather than a repository-pair score.

```text
Mechanism A emits X
Mechanism B requires Y
```

If `X` cannot satisfy `Y`, Archotraz records a specific composition hole and may search for the smallest missing bridge:

```text
X
-> format conversion?
-> semantic mapping?
-> metadata enrichment?
-> permission transition?
-> Y
```

The valuable candidate may therefore be an adapter or third mechanism rather than either original repository.

No bridge is treated as established until supported by evidence or measured behavior.

## Transformation algebra

The semantic model should support multiple execution interpretations without multiplying infrastructure. Conceptually useful composition operators include:

- sequence: `A >> B`;
- parallel/independent: `A || B`;
- composition/integration: `A tensor B`;
- alternatives: `A | B`;
- repeat/fixed point: `A*`;
- conditional/guarded execution: `?A`;
- falsification intent: `!A`.

These are design semantics, not a commitment to Python operator overloading or a specific DSL in the first implementation.

A single transformation graph may therefore be rendered as a pipeline, compiler schedule, search graph, execution DAG, or experiment plan depending on the lens.

## Separate semantics from execution

A semantic transformation describes what result is required. Execution policy decides how to obtain it.

The same transformation may be satisfied by:

- an existing valid cached result;
- a local deterministic implementation;
- an external analyzer;
- a Bopo-executed effect;
- a sandboxed probe;
- a human-supplied observation.

The method used must remain visible in evidence and receipts.

This permits sequential, parallel, lazy, streaming, cached, local, sandboxed, dry-run, and later remote execution without changing the semantic meaning of the case.

## Content-addressed and incremental behavior

Where practical, derived entities and transformation outputs should use identities derived from canonicalized content plus relevant semantic versions.

The design goal is:

```text
same semantic inputs
+ same transformation version
= same derivation identity
```

This supports deduplication, reuse, cache identity, reproducibility, and change detection.

Transformations should emit deltas. When source or evidence changes, Archotraz follows lineage to mark only dependent descendants stale and recomputes only what is required.

This makes provenance a dependency graph and incremental-computation engine.

## Virtual universes and bounded work

A mathematically complete search universe must not require materializing all of its members.

A CandidateUniverse should support:

- stable universe identity/version;
- explicit membership/inclusion rule;
- deterministic ordering/addressing;
- total count where computable;
- cursor/batch traversal;
- coverage accounting;
- views for inspected, constrained-out, deferred, sentinel, and uninspected regions.

The system must distinguish:

```text
complete universe definition
!=
complete evaluation
```

Peak RAM for pair traversal must remain bounded independently of the Cartesian search-space size.

## Failure certificates and Failure Atlas

Failure should become reusable negative knowledge rather than a dead-end label.

A failure certificate should identify the narrowest supported failing condition, including relevant mechanisms, adapters, workload, environment, and evidence.

Future configurations matching that condition may be pruned or deprioritized without rerunning the same failed experiment, while the underlying components remain eligible in materially different contexts.

A Failure Atlas is a rebuildable projection over such receipts/certificates rather than a separate truth store.

## Search-policy innovation

Search policy itself is experimental.

New policies begin in shadow mode where practical:

- the current policy controls real investigation;
- shadow policies record what they would inspect;
- shared selections may reuse the same probes;
- disagreements receive a bounded evaluation budget;
- sentinel/opposition probes deliberately sample regions the current policy considers unpromising.

Policy bakeoffs use the same frozen universe and comparable resource budgets. Measurements remain multidimensional: useful discoveries, misses, wall time, CPU, peak RAM, analyzer calls, cost, and coverage. These should not immediately collapse into one composite score.

A policy change is promoted only on protected evaluation.

## Self-compression

Because workflows are represented as transformations with receipts, Archotraz may later inspect its own repeated behavior.

Candidate self-optimizations include:

- fuse operations that are always executed together and duplicate work;
- compile frequently repeated verified chains into decomposable macro-operations;
- replace frequently repeated adapter chains with a directly synthesized/tested bridge;
- identify analyzers or operations that add no measured marginal information;
- rewrite execution graphs for parallelism, caching, or conditional escalation.

Archotraz must test such self-rewrites against baseline behavior before promotion. Self-optimization is not exempt from Archotraz's own evidence rules.

## Operator model: Case as the front door

The operator should work primarily with a Case, not internal pipeline stages.

A Case File is a rebuildable human-readable projection that answers:

1. What are we trying to accomplish?
2. What is known?
3. What remains unknown?
4. What has already been tried?
5. What can I do next?

Progress must report epistemic/search accounting rather than opaque percentages, including defined universe, inspected candidates, constraint exclusions, deferred/uninspected regions, viable configurations, falsified configurations, and blockers.

Operator controls should act on the option space: select, compare, combine, exclude, defer, reopen, expand, show unknowns, and request investigation. Warden and execution policy determine which internal transformations are required.

Before side-effecting execution, the operator receives a preview of components, versions, permissions, resource budget, expected artifacts, known unknowns, and rollback/recovery information.

A Case must resume from durable verified state without chat reconstruction.

## Capability Cards and Interaction Recipes

Documentation is a build output, not post-development cleanup.

Each operator-visible transformation should expose one shared operation definition from which practical surfaces may be generated where feasible:

- CLI help;
- input/output schema;
- Capability Card;
- worked example;
- permission preview;
- smoke-test fixture;
- recovery guidance.

A Capability Card answers:

- what can this do?
- how do I start it?
- what inputs are required?
- what will I receive?
- how do I interpret the result and UNKNOWN?
- what can fail and what is the recovery action?
- what has this operation not established?

A Mechanism Passport may additionally expose an Interaction Recipe: the smallest verified invocation, minimal valid input, expected output, verification check, required permissions, common failure, recovery action, and exact versions against which it was verified.

## Resource invariants

Phase 2 adopts these resource laws:

1. avoid work before optimizing work;
2. do not materialize an entire universe merely because it is defined;
3. bound RAM independently of corpus/search-space cardinality for ingestion, traversal, projection, and inspection;
4. cache only with exact reusable identity;
5. derived caches/projections are disposable, canonical evidence is not;
6. performance measurements remain measurements, not automatic decision authority;
7. transformations declare stream/batch behavior and resource/effect classes;
8. representative runs record wall time, CPU, peak RAM, database growth, calls/reuse, search coverage, and audit misses where applicable.

## Canonical versus projected state

The long-term simplification target is to minimize canonical concepts. Phase 2 should evaluate whether most operator and analysis surfaces can be reconstructed from a small canonical core such as:

```text
versioned entities
+ evidence/events
+ transformation receipts
```

The following should preferentially remain rebuildable projections unless evidence shows they require canonical ownership:

- Feature Matrix;
- Case File;
- Mechanism Passport presentation;
- Failure Atlas;
- progress dashboards;
- policy reports;
- performance dashboards;
- search-space views.

This is a design direction, not authorization to rewrite the existing eight-table ledger in one migration.

## Development strategy

Do not rewrite the verified foundation wholesale.

The migration strategy is incremental:

1. preserve current merged behavior;
2. treat the current Processor Matrix as a small-batch projection experiment;
3. introduce shared transformation/receipt semantics around existing operations before replacing algorithms;
4. add versioned identity and lineage when the first real mechanism/target slice requires them;
5. implement bounded reads/streaming before corpus-scale use;
6. build one real Case end-to-end before broad UI work;
7. activate later gates only when their tripwire is reached.

## Trigger ledger

Known future concerns become explicit tripwires rather than immediate prerequisites.

Examples:

- first canonical schema change -> migration gate;
- first untrusted executable analysis -> sandbox/capability gate;
- first corpus-scale pair run -> virtual-universe/bounded-traversal gate;
- first adaptive Kitchen search -> protected-evaluation gate;
- first competing search policies -> shadow-policy/sentinel gate;
- first large analyzer artifacts -> content-addressed artifact-storage gate;
- first long-running autonomous work -> lease/checkpoint/resume gate.

## Immediate Phase 2 bounded sequence

The next implementation plan should minimize simultaneous novelty.

### Slice 1 — Matrix projection checkpoint

Finish or disposition the existing `feature/processor-feature-matrix` bounded work as a small-batch projection. Explicitly label it non-corpus-scale.

### Slice 2 — Shared transformation receipt contract

Introduce the smallest operation/receipt schema capable of wrapping one existing operation without changing its algorithm. Capture semantic version, exact inputs, outputs, status, and baseline resource metrics. Generate one Capability Card from that contract where practical.

### Slice 3 — Versioned snapshot + lineage proof

Create one exact RepositorySnapshot and one lineage-linked derived observation. Change the snapshot/source and demonstrate selective invalidation of only its descendants.

### Slice 4 — Mechanism + Target + Case proof

Create one Target, one or two evidence-backed Mechanism entities/passports, one unresolved Hole, and one Case File projection showing knowns, unknowns, and next actions.

### Slice 5 — Directed bridge/configuration proof

Represent one directed integration edge, one missing-bridge condition if needed, and one inspectable CandidateConfiguration. No global ranking is required.

### Slice 6 — Bounded work proof

Demonstrate cursor/batch traversal and bounded RAM over a virtual candidate universe, with coverage accounting.

Only after these proofs should the project decide whether a dedicated DSL, graph backend, scheduler, broad UI, MAP-Elites, EIG scheduler, SMT layer, or other sophisticated mechanism has earned implementation.

## Acceptance criteria

The Phase 2 architecture is successful when one real Case can demonstrate all of the following without chat reconstruction:

- a named target/workload;
- exact source/version identities;
- mechanism-level rather than repository-only reasoning;
- evidence lineage and explicit UNKNOWN holes;
- at least one transformation graph interpretable through more than one lens;
- receipts sufficient to reproduce and resume work;
- bounded resource behavior for traversal/projection;
- a human-readable Case File with next permissible actions;
- one inspectable directed configuration hypothesis;
- a capability/interaction recipe for an operator-visible result;
- no score or prediction silently promoted into evidence;
- no requirement that an entire combinatorial universe fit in memory.

## Explicit non-goals for the first implementation plan

Do not add merely because this design mentions them:

- microservices;
- Kubernetes;
- a new canonical database;
- full React UI;
- full autonomous agent swarm;
- a custom DSL;
- MAP-Elites in production authority;
- learned scheduling;
- SMT dependency;
- complete self-rewriting architecture;
- Work Release automation;
- public productization.

Those remain experimental options or later gates.
