# Archotraz Phase 2 — Polymorphic Transformation Kernel

Status: **DESIGN SPEC — USER REVIEW REQUIRED BEFORE IMPLEMENTATION PLAN**

Base checkpoint:

```text
main = a48906982f003ee2ef8aca02b129299f8301fa3b
```

This design preserves the existing merged bootstrap foundation. It does not reinterpret merged evidence as wrong, replace SQLite as canonical truth, or collapse the existing stage vocabulary. It defines the next architecture layer so that Archotraz can support pipeline, compiler, search, experiment, build, dependency, learning, and operator views without building separate infrastructures for each.

---

## 1. Objective

Archotraz must let one operator move from:

```text
I have a problem
```

to:

```text
I have a working, justified configuration,
I know why it exists,
I know what remains unknown,
and I can resume or improve it later.
```

The Phase 2 design must also keep resource use bounded, preserve unusual candidates, avoid repeated work, support incremental recomputation, and allow Archotraz to evaluate and improve its own search methods.

The design goal is therefore not to add many independent subsystems. It is to establish a small semantic substrate from which those capabilities can be projected.

---

## 2. Core design law

No single architectural metaphor owns Archotraz.

The same underlying state may be interpreted as:

- a pipeline;
- compiler passes;
- a search space;
- a dependency graph;
- an experiment plan;
- an execution DAG;
- a build system;
- a learning loop;
- a case file for the operator.

These are **lenses over shared state and transformation semantics**, not separate application models.

Therefore:

> If multiple useful interpretations can share the same underlying state, evidence, lineage, and receipts, Archotraz must preserve those interpretations rather than forcing one to own the others.

---

## 3. Architectural substrate

Phase 2 centers on five operator/domain primitives and three lower-level semantic primitives.

### 3.1 Operator/domain primitives

```text
CASE
OBJECT
EVIDENCE
OPERATION
RECEIPT
```

These are the primary developer-facing abstractions.

### 3.2 Lower-level semantic primitives

Conceptually, the five primitives reduce to:

```text
STATE
TRANSFORMATION
PROVENANCE
```

This lower level is a design constraint, not a requirement to expose a generic graph database or rewrite every existing table immediately.

The implementation should remain concrete and typed. The purpose of the reduction is to prevent duplicated infrastructures.

---

## 4. Case

A **Case** is the operator's front door and resumable unit of work.

A Case answers:

```text
What are we trying to accomplish?
What is known?
What is unknown?
What has been tried?
What candidates/configurations exist?
What can happen next?
```

Minimum conceptual state:

```text
Case
├─ case_id
├─ goal
├─ TargetSpec reference
├─ constraints
├─ CandidateUniverse reference(s)
├─ current candidate/configuration references
├─ unresolved holes
├─ current verified checkpoint
├─ pending/permitted actions
└─ operator feedback references
```

A Case is not an alternate truth store. Its human-readable Case File is a rebuildable projection from canonical evidence, objects, operations, and receipts.

The operator should not need to decide whether to invoke Detective, Processor, Guard, Kitchen, or another internal stage. The operator acts on the Case and Archotraz determines the internal transformations required.

---

## 5. Object

An **Object** is a versioned, typed thing Archotraz can reason about.

Conceptual envelope:

```text
Object
├─ object_id
├─ kind
├─ schema_version
├─ content/version identity
├─ payload
└─ provenance references
```

Initial and future object kinds include:

```text
repository
repository_snapshot
mechanism
target
candidate_universe
integration_edge
configuration
benchmark
environment
artifact
```

Object kinds retain strongly typed payloads. The shared envelope prevents each kind from requiring its own identity, versioning, caching, and provenance infrastructure.

Content-addressed identity should be used where safe and useful for immutable or derived objects. The identity must include every input that materially changes meaning, including relevant contract/schema/tool versions.

---

## 6. Evidence

Evidence is the canonical answer to:

```text
What is asserted about which subject, on what basis?
```

Conceptual shape:

```text
Evidence
├─ evidence_id
├─ subject_id
├─ assertion/property
├─ epistemic state
├─ value
├─ source
├─ derived_from[]
├─ method/contract version
├─ subject version
└─ observed_at
```

Initial epistemic states may remain small, but the model must be evolvable beyond the current Processor states.

Expected eventual distinctions include:

```text
OBSERVED
DECLARED
INFERRED
UNKNOWN
NOT_APPLICABLE
CONFLICTED
STALE
SUPERSEDED
```

### 6.1 Evidence lineage

`derived_from` lineage must support two jobs:

1. explanation and corroboration analysis;
2. selective invalidation/reprocessing.

Representative chain:

```text
repository snapshot
→ source span
→ mechanism claim
→ normalized feature
→ integration-edge proposal
→ configuration
→ experiment result
```

If an upstream source changes, Archotraz marks dependent derived evidence stale and recomputes only the affected descendants. Historical evidence and historical experiment receipts are preserved.

Repeated analyzer statements with shared ancestry must not count as independent corroboration merely because they were produced by separate workers.

---

## 7. Unknowns as first-class holes

`UNKNOWN` must remain an epistemic state, but Phase 2 also models decision-relevant unknowns as **Holes**.

Conceptually:

```text
Hole
├─ hole_id
├─ required fact/constraint
├─ blocking object/decision
├─ candidate resolver operations
└─ current status
```

Example:

```text
unknown interface schema
→ inspect exported type
→ static parser
→ code graph
→ sandboxed probe
→ operator judgment
→ remain unknown
```

The scheduler does not ask "What can we analyze next?" in the abstract. It asks:

> Which unresolved Hole blocks the current objective, and what is the cheapest permitted operation likely to resolve it?

An estimated information value may schedule work later, but it never becomes evidence that a mechanism works.

---

## 8. Operation

An **Operation** is a bounded transformation over Archotraz state.

Conceptual contract:

```text
OperationDefinition
├─ operation_id
├─ version
├─ consumes
├─ produces
├─ preconditions
├─ authority boundary
├─ permissions/capabilities
├─ deterministic / seed policy
├─ max_batch_size
├─ streamable
├─ estimated_peak_ram
├─ estimated cost class
├─ cache identity inputs
├─ failure modes
├─ example
└─ documentation metadata
```

Existing concepts such as Detective, Processor extraction, Matrix projection, Cell placement, pair enumeration, future mechanism extraction, edge inspection, Kitchen tests, and benchmarks become Operations or families of Operations.

This does **not** erase stage ownership. Stage ownership remains a policy/lens telling Archotraz which operations may run and what authority their outputs possess.

### 8.1 Pure versus effectful operations

Operations should be pure when practical:

```text
Output = F(Input identities, Operation version)
```

Pure operations are naturally memoizable, replayable, parallelizable, and content-addressable.

Effectful operations include network fetches, package installation, sandbox execution, source mutation, publication, and other external side effects. They require explicit Warden capability authorization and stronger receipts.

### 8.2 One definition, many generated surfaces

Where practical, one OperationDefinition should generate or feed:

- CLI command/help;
- input validation;
- machine schema;
- Capability Card;
- execution/permission preview;
- worked example;
- smoke-test fixture;
- UI form/control metadata;
- receipt schema expectations.

This prevents CLI, UI, documentation, examples, and runtime contracts from drifting independently.

---

## 9. Receipt

Every Operation emits a **Receipt**.

Conceptual shape:

```text
Receipt
├─ receipt_id
├─ operation id/version
├─ exact input identities
├─ status
├─ exact output identities
├─ evidence created
├─ started/finished
├─ wall time
├─ CPU time
├─ peak RAM
├─ I/O / external cost where measurable
├─ cache hit/miss/reuse status
├─ permissions actually used
├─ failure attribution
└─ verification metadata
```

Receipts unify:

- reproducibility;
- performance instrumentation;
- debugging;
- progress reporting;
- resume behavior;
- experiment history;
- policy telemetry;
- failure knowledge;
- verification receipts.

Receipts are measurements/events. They are not automatically recommendations or evidence that a candidate is good.

---

## 10. Polymorphic lenses

The same state/transformation graph may be rendered through multiple lenses.

### Pipeline lens

Shows ordered stage/progress flow.

### Compiler lens

Shows transformations from problem/specification to normalized representations and executable configurations.

### Dependency lens

Shows what must be invalidated/recomputed when an upstream object/evidence item changes.

### Search lens

Shows candidate universe, explored regions, exclusions, alternatives, and sentinels.

### Experiment lens

Shows hypotheses, falsification attempts, benchmarks, baselines, and protected evaluation.

### Execution lens

Shows ready operations, dependencies, resource needs, permissions, and concurrency.

### Operator/Case lens

Shows goal, knowns, unknowns, candidates, progress, next actions, and deliverables.

No lens may silently create a second state model.

---

## 11. Transformation composition

Archotraz should support composable transformation semantics without forcing a single notation into the public operator interface.

Conceptually useful compositions include:

```text
A >> B    sequential composition
A || B    independent/parallel work
A | B     alternatives / competing hypotheses
A ⊗ B     attempted integration/composition
A*        repeat to fixed point / stopping condition
?A        conditional/guarded transformation
!A        adversarial/falsification transformation
```

These operators are conceptual semantics first. Implementation syntax may differ.

A composed transformation can be interpreted simultaneously as a pipeline, execution DAG, compiler schedule, experiment plan, and progress model.

---

## 12. Work Graph

For a Case, Archotraz compiles currently required work into a DAG of Operations.

A node is ready when:

```text
required inputs exist
preconditions hold
permissions permit execution
resource budget admits it
and no valid reusable result already satisfies it
```

The Work Graph enables:

- resumability;
- parallel execution;
- bounded concurrency;
- selective recomputation;
- dependency invalidation;
- progress reporting;
- cache reuse;
- failure propagation.

The Work Graph is derived state and must be rebuildable from canonical state and policy.

---

## 13. Typed mechanism contracts and missing-bridge search

Mechanisms should progressively expose typed contracts rather than relying only on whole-repository compatibility.

A Mechanism Passport should identify:

```text
mechanism identity
repository snapshot
module/symbol/source scope
accepted inputs
emitted outputs
constraints
supporting evidence
unknowns
measured costs where measured
known adapters
known failures
verified interaction recipe
```

Composition asks:

```text
Does output type/contract X satisfy input type/contract Y?
```

If not, the mismatch becomes a structured **bridge requirement** rather than an immediate dead end.

Archotraz then searches the mechanism corpus for the smallest known transformation capable of satisfying the mismatch. If none exists, it may later propose an adapter hypothesis, which remains unverified until tested.

This turns compatibility search into constrained composition rather than arbitrary pair scoring.

---

## 14. Virtual Candidate Universe

A CandidateUniverse is a versioned virtual object.

It defines:

```text
universe_id
corpus revision
membership/inclusion rule
exclusion rule
ordering
count
selection provenance
```

Complete definition does not imply complete materialization or evaluation.

For pair universes, a deterministic address maps a universe plus member indices/identities to a pair without storing every pair.

Archotraz reports separately:

```text
universe defined
candidates/pairs visited
excluded by proven constraints
deferred by policy
sentinel sampled
uninspected
```

This preserves honest coverage while keeping memory bounded.

---

## 15. Resource laws

### 15.1 Avoid work before accelerating work

Preferred order:

```text
reuse valid prior work
→ selectively invalidate
→ apply proven cheap constraints
→ resolve blocking holes
→ spend expensive analysis only on survivors
→ optimize hot execution paths only after measurement
```

### 15.2 Bounded memory

Corpus size and pair-universe size must not require proportional in-memory materialization for traversal or inspection.

Large matrices, pair spaces, result sets, and artifact collections must support bounded batches, streaming, cursors, or rebuildable external projections.

### 15.3 Derived data is disposable

Eviction priority begins with temporary buffers, caches, indexes, and rebuildable projections. Canonical evidence and hard-won experiment records are not discarded to improve performance.

### 15.4 Performance remains multidimensional

Do not collapse performance into one new compound score.

Track primitive dimensions such as:

```text
wall time
CPU time
peak RAM
database/artifact growth
analyzer calls
cache hit/miss
universe defined/visited/excluded
experiment cost
useful discoveries
valuable misses found by audit/sentinels
```

The optimization target is time/cost to a trustworthy useful result under explicit coverage and miss constraints.

---

## 16. Failure certificates and Failure Atlas

Failure must become reusable knowledge.

A failed configuration should be minimized where feasible into a **FailureCertificate** describing the smallest known condition that reproduces the failure.

Conceptually:

```text
FailureCertificate
├─ involved object/configuration identities
├─ target/workload/environment
├─ minimal failing condition
├─ failure attribution
├─ supporting receipt(s)
└─ scope/limitations
```

The Failure Atlas is a projection over FailureCertificates and failure receipts.

A certificate may prune future work only when its conditions actually match. It must not globally blacklist a component from a context-specific failure.

---

## 17. Innovation loop around Archotraz itself

Search policy is itself experimental.

### 17.1 Policy telemetry first

Record why a policy selected, deferred, or excluded a candidate; its estimated cost; and the evidence available at the time.

### 17.2 Opposition/sentinel budget

Every serious search policy reserves a bounded budget for deliberately testing regions it considers unlikely, including excluded, poorly documented, unusual, or previously failed candidates under changed conditions.

Unexpected value discovered by sentinels is evidence against the current policy.

### 17.3 Shadow tournaments

New policies begin in shadow mode against the same frozen CandidateUniverse.

They record what they would investigate without immediately receiving full authority. Bounded real resources may be allocated to disagreements and sentinel samples.

Policies are compared on primitive dimensions such as discoveries, misses, elapsed time, RAM, and cost.

### 17.4 Sophistication must earn authority

MAP-Elites, uncertainty-first search, EIG/VOI scheduling, Hyperband-like allocation, SMT assistance, surrogates, and other advanced techniques remain candidate Operations/policies until they outperform simpler baselines under protected evaluation.

No sophisticated method receives authority because of theory or novelty alone.

---

## 18. Self-compression and macro operations

Because Archotraz records Operation graphs and Receipts, it may later identify repeated or redundant internal work.

Candidate optimizations include:

```text
repeated operation chain
→ MacroOperation

repeated adapter chain
→ candidate direct adapter

expensive operation with no decision impact
→ conditionalize/defer/remove

duplicate analyzers
→ benchmark and consolidate
```

Any self-rewrite is proposed and benchmarked first. Archotraz does not silently mutate its own authoritative architecture.

---

## 19. Operator spine

The operator should interact with Cases and options, not internal stage plumbing.

Expected high-level controls include:

```text
Select
Select Several
Combine
Compare
Exclude
Defer
Reopen
Expand Family
Expand Node
Show Next K
Show All
Show Constrained
Show Unknowns
Missing Shape
None of These
```

The Warden and Work Graph translate those intents into permitted internal Operations.

### 19.1 Case File

The Case File is the central human-readable projection.

It must make visible:

```text
goal
current verified state
known evidence
unknowns/holes
candidate/search coverage
competing configurations
recent investigations and failures
resource use
next permissible actions
```

Progress must be factual and countable rather than an opaque percentage.

### 19.2 Explanation at action point

Every proposal should expose:

```text
why it exists
what evidence supports it
what remains unknown
what could falsify it
what it costs to learn more
what happens if selected
```

### 19.3 Execution preview

Before effectful work, show exact planned components, source versions, operations, permissions, resource budget, expected outputs, and unresolved risks.

### 19.4 Resume

Reopening a Case must restore the last verified state and next permissible actions without chat reconstruction.

---

## 20. Capability Cards and Interaction Recipes

Documentation is a build artifact, not post-development homework.

Every new operator-visible capability must ship with a Capability Card answering:

```text
What can it do?
How do I start it?
What inputs are required?
What output will I receive?
How do I read the output?
What can go wrong?
How do I recover?
What does this operation NOT establish?
```

Where practical, the card, CLI help, UI metadata, and examples derive from the OperationDefinition.

A Mechanism Passport should also expose an Interaction Recipe describing the smallest verified invocation, example input/output, success check, common failure, recovery step, required permissions, and verified source/environment versions.

---

## 21. Human Operability Gate

A capability is not complete merely because its automated tests pass.

For operator-visible slices, a cold-start walkthrough must prove that from a clean checkout and repository-owned documentation the operator can:

1. find/open the relevant Case;
2. understand the current state without chat history;
3. identify what remains UNKNOWN;
4. perform the documented operation;
5. inspect the documented result;
6. understand what the result does not prove;
7. recover from at least one documented failure path where relevant;
8. resume the Case without remembering prior commands.

If remembered chat context is required, the capability is incomplete.

---

## 22. Canonical versus projected state

The design strongly prefers a small canonical core and many rebuildable projections.

A future convergence target is:

```text
canonical:
  objects / identity-bearing state
  evidence/events/lineage
  receipts/attempt history

rebuildable projections:
  Case File
  Feature Matrix
  Mechanism Passport view
  Failure Atlas
  Candidate Universe views
  progress dashboards
  search-policy reports
  Capability Cards
```

This is a direction, not authorization to rewrite the existing SQLite schema immediately.

Merged tables and evidence semantics remain authoritative until an explicit migration design is approved.

---

## 23. Compatibility with current merged code

Current merged modules are not discarded.

Phase 2 initially adapts existing behavior behind shared operation contracts rather than rewriting algorithms:

```text
ingest-repo
Detective triage
Processor feature extraction
Processor matrix projection
Cell Housing
pair enumeration Guard
Bopo health/preflight
```

The existing Matrix implementation is accepted as a small-batch proof of rectangular `X/M` semantics. It must not be treated as the corpus-scale matrix engine because its current implementation materializes selected rows/masks and scans observations in memory.

No immediate rewrite is required until the bounded-traversal/performance gate is activated.

---

## 24. Trigger ledger instead of giant prerequisite list

The previous audit remains useful as a trap inventory, not a build order.

Each concern receives an activation trigger.

Examples:

```text
WHEN canonical schema first changes
THEN migration/refusal gate activates

WHEN multi-row canonical writes become nontrivial
THEN atomic/resumable unit-of-work gate activates

WHEN untrusted code/build/test execution begins
THEN hostile sandbox + capability gate activates

WHEN candidate universes exceed bounded materialization
THEN virtual traversal gate activates

WHEN Kitchen adapts repeatedly to benchmark feedback
THEN protected-evaluation/selection-history gate activates

WHEN multiple policies steer search
THEN shadow-tournament gate activates
```

This keeps all known risks without pretending all must be built now.

---

## 25. Phase 2 implementation slices

The implementation sequence is intentionally smaller than the design surface.

### Slice 1 — Kernel contracts and repository-owned checkpoint

Implement minimal typed contracts for:

```text
Case
Object identity envelope
OperationDefinition
Receipt
```

and define how existing canonical EvidenceLedger evidence is referenced without replacing it.

Add a repository-owned current-state checkpoint containing main SHA, accepted authority rules, active slice, superseded development paths, and next gate.

No search algorithm changes.

### Slice 2 — Adapt existing operations

Wrap existing merged capabilities as OperationDefinitions without rewriting their internal algorithms.

Generate or validate Capability Cards and uniform Receipts for the adapted operations.

### Slice 3 — First real Case

Using one actual target:

```text
Case
→ RepositorySnapshot(s)
→ evidence-backed Mechanism Passport(s)
→ TargetSpec
→ one directed IntegrationEdge
→ one inspectable CandidateConfiguration
```

The Case File must show knowns, unknowns, evidence lineage, search coverage, and next permissible actions.

### Slice 4 — Instrument and bound

Measure existing operations and introduce only the performance changes justified by measurements:

```text
bounded ledger reads
streaming/batched matrix work
virtual pair traversal
selective invalidation/reprocessing
exact reusable result identities
```

### Slice 5 — Innovation telemetry

Add policy-decision receipts, sentinel probes, failure certificates, and shadow-policy comparison infrastructure.

Kitchen and effectful construction remain behind their later gates.

---

## 26. Acceptance criteria for the architectural transition

Phase 2 kernel transition is successful when all of the following can be demonstrated without introducing a broad UI or autonomous agent system:

1. One Case can be reopened without chat reconstruction.
2. Existing operations can be represented through one shared OperationDefinition contract.
3. Every adapted operation emits a uniform Receipt with identity, result, and resource measurements where measurable.
4. Derived views can be regenerated from canonical state rather than becoming alternate truth stores.
5. One RepositorySnapshot can support a source-bound Mechanism Passport.
6. One TargetSpec can be used to construct one inspectable directed configuration hypothesis.
7. Unsupported assertions remain explicit UNKNOWN/Holes.
8. The same underlying state can be rendered at least as Case, pipeline/progress, dependency/lineage, and execution views without duplicated state models.
9. A repeated pure operation with identical material identity can be recognized as reusable rather than recomputed.
10. A small corpus traversal can report defined, visited, excluded, deferred, and uninspected space separately.
11. A cold-start Capability Card example can be followed from a clean checkout.
12. No new compound authority score or score-on-score epistemology is introduced.

---

## 27. Explicit non-goals for the first kernel implementation

Do not introduce in the first implementation slice:

- microservices;
- Kubernetes;
- a new canonical database;
- a graph database as truth owner;
- a broad React/web UI;
- autonomous agent swarms;
- full Kitchen;
- hostile-code execution;
- full mechanism ontology;
- MAP-Elites/Hyperband/EIG as production authority;
- general self-modification;
- a rewrite of already-verified modules solely for architectural cleanliness.

The kernel exists to make later capabilities cheaper to add, not to front-load them.

---

## 28. Design summary

Archotraz Phase 2 is a **self-describing transformation system**.

Its state can be interpreted as pipelines, compiler schedules, search spaces, experiments, dependency graphs, and execution plans according to the problem being solved.

The implementation remains deliberately small:

```text
CASE
OBJECT
EVIDENCE
OPERATION
RECEIPT
```

with shared transformation/provenance semantics underneath.

From that substrate, Archotraz derives:

```text
Case Files
Feature Matrices
Mechanism Passports
Candidate Universes
Integration Edges
Failure Atlas
Capability Cards
Interaction Recipes
progress views
performance reports
policy bakeoffs
```

The governing principle is:

> Build the semantic substrate once; make pipelines, compilers, searches, experiments, documentation, and operator views different interpretations of it rather than different systems.
