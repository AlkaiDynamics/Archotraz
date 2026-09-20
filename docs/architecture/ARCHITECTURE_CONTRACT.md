# Archotraz Architecture Contract

Status: **FROZEN BASELINE FOR MVP IMPLEMENTATION**

This document records the authoritative architecture recovered from the project transcript and defines the implementation boundary for the first Archotraz build. It is intentionally conservative: confirmed decisions are separated from unresolved bindings, and deferred systems are not promoted into MVP prerequisites.

Implementation decision: the MVP executable baseline is **Python 3.12+ as a modular monolith**. This does not alter the frozen epistemic architecture; see [ADR-0001](./ADR-0001-python-modular-monolith.md).

## 1. System identity

Archotraz is a **stateful algorithmic search, routing, recombination, falsification, construction, and optimization machine**.

It is not primarily:
- an agent system;
- an AI coding platform;
- a repository recommender;
- or a conventional orchestration framework.

Repositories are evidence-bearing inputs, not the enduring unit of intelligence. The durable unit is **system state**: mechanisms, observations, failures, interfaces, pairings, configurations, and measured outcomes.

Primary loop:

```text
REPRESENT
→ SEARCH
→ MATCH
→ GROUP
→ FALSIFY
→ BUILD
→ MEASURE
→ LEARN
→ RECOMBINE
```

Optimization objective:

> Discover and construct configurations that deliver the greatest useful capability and quality with the least latency, computation, operational debt, integration friction, and cost, while retaining enough evidence to justify why the configuration should exist.

## 2. Governing laws

### 2.1 Algorithms first

The active machine is algorithmic.

- Manual repository entry is the current operating mode.
- Agents may later exist behind bounded doors.
- Agents are not foundational to the MVP.
- Bopo is the selected local runtime/control shell.
- Taskade-style normalization is a later optional boundary extension.

### 2.2 Preserve the search space

Ranking does not imply deletion.

Repository/tool population:
- KEEP
- donate/harvest population
- trash

Algorithm population:
- KEEP
- Algo Bucket / Psych Ward
- The Hole for repeatedly unproductive but legitimate algorithms
- no automatic deletion merely because a standalone algorithm underperforms

A weak standalone algorithm may become valuable when paired with another objective, constraint, guard, or representation.

### 2.3 Evidence before authority

The following are distinct objects:

```text
MEASUREMENT ≠ DERIVED METRIC ≠ PREDICTION ≠ DECISION
```

A score is not evidence.
A prediction is not a measurement.
A repeated claim is not independent corroboration.

### 2.4 No score-on-score epistemology

Production authority begins from primitive observations and independently grounded measurements.

Compound heuristic chains may be researched in shadow mode, but they do not receive production authority merely because their outputs are numerically convenient.

## 3. Frozen component register

### 3.1 Runtime and control

| Component | Role | Authority |
| --- | --- | --- |
| Bopo | local runtime/control shell | CONFIRMED |
| Warden | control plane for policies, movement, replay, simulation, visibility | CONFIRMED |
| SQLite | canonical evidence/state foundation | CONFIRMED |
| Taskade-style normalization | optional future integration boundary | DEFERRED |

### 3.2 Evidence-acquisition stages

| Stage | Role | Cost/authority rule |
| --- | --- | --- |
| Detective | cheap triage from metadata, README/package data, obvious source signals | must not have enough authority to cheaply reject valuable candidates from insufficient evidence |
| Adjudicator | deeper structural examination | decides whether deeper inspection is warranted |
| Intake | full repository understanding / "strip search" | owns expensive repository analysis |
| Processor | converts Intake evidence into structured state | must not rediscover/reopen source code as part of normal operation |

### 3.3 Retained analytical functions

| Function | Retained role |
| --- | --- |
| CodeGraph | exact local source topology: AST, symbols, references, call/dependency relationships, blast radius |
| Graphify | broader architecture / heterogeneous repository knowledge graph |
| codebase-memory-mcp | fast persistent structural retrieval |
| RepoWise | history, change risk, test reachability, code-health trajectory |
| SocratiCode | deep semantic/call-flow/impact escalation |
| Repomix | very cheap repository packaging/intake |
| REA | behavioral/black-box reconstruction where source evidence is insufficient |
| repX | binary/native/IR reconstruction |

CodeGraph and Graphify are complementary, not interchangeable.

### 3.4 Native mechanisms to harvest

These concepts are retained as local mechanisms when carrying an entire donor platform would create more debt than value:

| Donor concept | Native mechanism |
| --- | --- |
| RepoAtlas | survey → domains → map/tree → validate → query → refresh |
| AgentSmith | structure → functional domains → capabilities/interfaces/handoffs |
| FossilAI | holistic interpretation → constrained typed mechanism extraction |
| Codemap | functional modules + health/debt + repair/regression analysis |
| GitVoyant | temporal trajectory / deterioration / improvement |
| CodeMesh | unknown → investigate → verify → document → persist → reuse |
| Orbit | hard gates, bounded evidence, resource limits, false-completion prevention |
| fspec | invariant → acceptance criteria → code/test traceability |
| CLI-Anything | capability → normalized deterministic callable surface |
| Miniforge | bounded modification → build → diagnose → repair → retest |

Adoption gradient:

```text
REFERENCE
→ VALIDATOR
→ DATA SOURCE
→ DEPENDENCY
```

Evidence requirements increase as a component moves to the right. Useful mechanisms may survive even when the parent dependency is rejected.

## 4. Frozen algorithm authority

### 4.1 KEEP — production-authorized families

#### Representation
- feature matrix;
- explicit missingness masks;
- one-hot and multi-hot encoding;
- pair feature tensor;
- primitive mechanism/target/have/need relationships;
- DataModel;
- AccessPattern;
- fidelity;
- debt.

Unknown must remain unknown. Missingness must never silently collapse to zero.

#### Exhaustive/basic
- exhaustive unordered pair enumeration;
- raw overlap;
- raw gap matching;
- mean;
- maximum;
- P90.

#### Search
- MAP-Elites;
- beam search;
- evolutionary search;
- GitRecombo;
- complement-aware mutation;
- contribution-based removal when grounded in primitives;
- multi-generation exploration.

#### Novelty/diversity
- behavior-space distance;
- kNN novelty;
- novelty archive;
- Pareto;
- DPP;
- greedy k-DPP MAP;
- RBF/Gaussian similarity;
- adaptive bandwidth;
- log-determinant diversity.

#### Fast discovery
- Aho-Corasick;
- trie;
- failure links;
- multi-pattern single-pass matching.

### 4.2 Needed native families

Identified as needed, but not all required for the first MVP:
- feasibility/constraint solving;
- falsification/null testing;
- contribution/ablation;
- counterfactual/uniqueness;
- robustness/sensitivity;
- evidence/provenance;
- empirical validation;
- calibration;
- semantic matching;
- unseen-space estimation;
- latent clustering;
- active investigation;
- minimal-set optimization.

### 4.3 Psych Ward — preserved, zero production authority

The following are preserved for shadow-mode testing, repair, recombination, or later promotion, but are not authoritative in production:

- Structural Potential;
- Stepping-Stone Value;
- Complementarity;
- Synergy Proxy;
- current Discovery Value;
- derived Gap Coverage;
- Bridge Density;
- Target/Mechanism Breadth scores;
- Family Diversity score;
- Downstream / Next-Step Opportunity;
- Graph Leverage;
- Directed Support;
- heuristic Component Contribution;
- Market Gravity;
- Big-Spender Affinity;
- repository traction as technical-quality input;
- uncertainty bonus;
- class novelty priors;
- AutoPower / current Autopilot profiles;
- current CHAIN / AND+ / AND? / UNKNOWN / OVERLAP / ALT logic;
- current Chain score;
- HITS;
- PageRank and dependency-reversed PageRank;
- Strassen-inspired recursive block intelligence;
- AlphaTensor-inspired decomposition.

Rule:

```text
BUCKET ≠ PRODUCTION AUTHORITY
```

## 5. Repository admission and election

### 5.1 Hard veto gates

Unweighted. A candidate may be eliminated regardless of aggregate score for failure of:
- accuracy/capability floor;
- security/supply-chain risk;
- license compatibility;
- evidence/verifiability;
- fundamental integration compatibility.

### 5.2 Survivor score

| Dimension | Weight |
| --- | ---: |
| Power / accuracy / comprehensiveness | 25 |
| Marginal unique value / irreplicability | 20 |
| Extensibility / compatibility | 15 |
| Lightweight / low debt | 15 |
| Speed / efficiency | 10 |
| Reproducibility / testability | 10 |
| Health / maturity | 5 |

Marginal value:

```text
MV(x | S) = V(S ∪ {x}) - V(S)
```

A technically excellent component can still have near-zero marginal value if its capability is already supplied by the selected configuration.

### 5.3 Mimicability is separate

Mimicability controls acquisition strategy rather than technical-quality score.

Routing baseline:

| Main score | Mimicability | Route |
| --- | --- | --- |
| 85–100 | 0–5 | CORE / KEEP |
| 85–100 | 6–10 | KEEP vs MIMIC |
| 70–84 | 0–5 | SPECIALIST / ESCALATION |
| 70–84 | 6–10 | MIMIC → DROP |
| 50–69 | 8–10 | MINE FEATURE → DROP |
| 50–69 | 0–7 | DROP unless genuinely irreplaceable |
| <50 | any | TRASH |

A candidate dominated on Power, Speed, Debt, Compatibility, and Marginal Value is removed from the election before further ranking.

## 6. Frozen stage ownership

Canonical forward path:

```text
MANUAL INPUT
→ REPO RECORD
→ DETECTIVE
→ ADJUDICATOR
→ INTAKE
→ PROCESSOR
→ CELL HOUSING
→ GUARD SYSTEM
→ KITCHEN
→ WORK RELEASE
→ REHAB
→ SPRING
→ PRODUCT / WORLD
```

Cross-cutting systems:
- WARDEN — control plane;
- EVIDENCE — truth/provenance spine;
- CODEMESH — persistent learning;
- ORBIT — hard gates / false-completion prevention;
- DRY MODE — capability safety policy;
- PSYCH WARD — experimental algorithms;
- THE HOLE — repeatedly unproductive algorithms;
- CONJUGAL — out-of-distribution/generalization testing.

### Stage invariants

**Detective**
- cheapest examination stage;
- cannot cheaply convert low evidence into irreversible rejection.

**Adjudicator**
- deeper examination;
- decides whether Intake is justified;
- does not replace Intake.

**Intake**
- owns expensive source, architecture, history, semantic, behavioral, and binary reconstruction.

**Processor**
- consumes Intake evidence;
- normalizes features, missingness, labels, pair tensors, entity mapping, evidence state, cell class, and transitions;
- source rediscovery downstream is an ownership violation.

**Cell housing**
- stores state/organization, not intelligence;
- classifications are views over evolving evidence, not permanent identities.

**Guards**
- operate against shared state;
- do not own canonical truth.

**Kitchen**
- falsifies configuration hypotheses before meaningful engineering effort.

**Work Release**
- constructs only configurations that survive Kitchen.

**Rehab**
- proves that the built artifact produced the claimed gain.

**Spring**
- verifies release readiness; a Rehab pass may still fail Spring.

## 7. Guard / worker contract

Every guard or worker must declare:

```text
Consumes
Produces
Objective
Constraints
Evidence Used
Confidence / uncertainty representation
Cost
Determinism / seed requirements
Escalation trigger
Declared duplicate/overlap
```

This contract exists so Archotraz can identify:
- duplicate work;
- orphan outputs;
- circular dependencies;
- unnecessary execution;
- ungrounded authority transfer.

### Guard responsibilities

**Matcher** — promising pairwise configurations.

**Explorer** — unusual/unseen opportunity space rather than merely top-ranked current candidates.

**Grouper** — pair → trio → stack → configuration.

**Validator** — whether a configuration is allowed and internally coherent.

**Adversary** — whether claimed value can be destroyed through nulls, ablations, substitutions, sensitivity, necessity, or uniqueness tests.

**Scorer** — thin layer over primitive normalized measurements, empirical effect sizes, calibrated probabilities where calibration exists, null percentile, robustness, marginal contribution, marginal uniqueness, and Pareto status.

Preferred ordering:

```text
Hard constraints
→ empirical dimensions
→ Pareto
→ robustness/sensitivity
→ bounded ranking if needed
→ DPP for presentation diversity
```

DPP controls diverse presentation, not truth.

## 8. Canonical evidence and memory schema

SQLite is the authoritative ledger.

Canonical evidence objects:

```text
SQLite Evidence Ledger
├─ observations
├─ claims
├─ failures
├─ attempts
├─ decisions
├─ supersessions
├─ contradictions
└─ provenance
```

Derived/rebuildable projections may include:
- FTS / BM25;
- structural graph;
- semantic/vector representation;
- temporal view;
- experience memory;
- cache.

Hard rule:

```text
projection fails → rebuild projection
canonical evidence fails → stop
```

No graph, vector store, cache, or heuristic output may silently become an alternative source of truth.

### Warden history rule

Warden may change current policy. It may not rewrite historical evidence to make current policy appear correct.

## 9. Canonical representation

Single-candidate state includes:

```text
Feature Matrix X
Explicit Missingness Mask M
Raw Mechanisms
Raw Targets
Raw Have
Raw Need
Raw DataModel
Raw AccessPattern
Raw Fidelity
Raw Debt
```

Pair representation:

```text
P_ij = f(X_i, X_j, M_i, M_j)
```

Pair features include:
- shared/orthogonal mechanisms;
- target overlap;
- need_i ↔ have_j;
- need_j ↔ have_i;
- DataModel fit;
- AccessPattern fit;
- fidelity floor;
- integration debt;
- redundancy;
- directional support.

## 10. Integration edge is first-class

This recommendation is adopted as an implementation constraint for future composition work because it preserves the recovered architecture without expanding product identity.

For a directed connection A → B, the edge should eventually retain measurable integration facts such as:
- output schema A;
- input schema B;
- adapter operations;
- serialization cost;
- copy count;
- latency;
- memory movement;
- runtime boundary;
- dependency conflict;
- permissions;
- side effects;
- failure semantics;
- recovery semantics;
- information/fidelity loss.

A configuration is therefore better represented as:

```text
A + Edge_AB + B
```

rather than pretending compatibility is a property of A+B alone.

## 11. Falsification and construction boundary

Kitchen gauntlet:

```text
Candidate Configuration
→ Hard Constraints
→ Null Baseline
→ Ablation
→ Counterfactual Substitution
→ Uniqueness / Necessity
→ Sensitivity
→ Robustness
→ fspec Invariants
→ Evidence Review
→ PROMOTE or REJECT
```

A heuristic result is a proposal, not authorization to spend engineering resources.

Work Release begins only after Kitchen survival.

Rehab then asks:

```text
Did the implemented configuration produce the expected gain?
```

A mandatory compression pass should remove any component, adapter, algorithm, service, or representation whose removal preserves the measured gain.

Target principle:

```text
maximum useful capability / minimum machinery
```

## 12. Dry Mode contract

Dry Mode is a capability policy, not merely a UI flag.

Continues:
- ingestion;
- Detective;
- Adjudicator;
- Intake;
- Processor;
- scoring;
- matching;
- grouping;
- simulation;
- Kitchen analysis;
- adversarial validation;
- metric collection.

Paused:
- source refactoring;
- reverse engineering that mutates/builds;
- Work Release;
- Rehab execution;
- Spring;
- external publication/marketing.

## 13. MVP execution path

The near-term implementation order is frozen as:

```text
1. FREEZE COMPONENT REGISTER
2. FREEZE ALGO KEEP / ALGO BUCKET
3. FREEZE STAGE OWNERSHIP
4. FREEZE EVIDENCE + MEMORY SCHEMA
5. FREEZE DOOR / WORKER CONTRACTS
6. MAP MVP EXECUTION PATH
7. SCAFFOLD BOPO + WARDEN
8. WIRE SQLITE LEDGER
9. MANUAL REPO INGEST
10. DETECTIVE
11. FIRST REAL CELL
12. FIRST REAL GUARD RUN
```

This document completes the repository-level freeze for steps 1–6.

The first valuable executable machine is:

```text
manual candidate
→ evidence
→ profile
→ cell
→ pair universe
→ guard proposals
→ inspectable Kitchen candidates
```

Not required before Start:
- automatic research;
- multi-agent autonomy;
- full Work Release automation;
- public-release automation;
- every identified statistical method.

## 14. First genuine success criterion

The MVP is not proven merely because a UI launches.

First meaningful proof:

```text
Candidate A
Candidate B
→ independently grounded profiles
→ matching primitives
→ candidate configuration
→ constraint validation
→ null / ablation / counterfactual challenge
→ Kitchen survival
→ bounded construction
→ benchmark against A
→ benchmark against B
→ benchmark against incumbent
→ measured improvement
→ retained provenance
→ new reusable mechanism/configuration
```

A valid successful outcome may be:

> A+B is worse than A alone; remove B.

Archotraz optimizes the configuration, not component count.

## 15. Runtime binding status

### Resolved — Bopo

The selected Bopo repository is:

```text
https://github.com/bopodev/bopo
```

The MVP integration boundary is frozen in [../integrations/BOPO_BINDING.md](../integrations/BOPO_BINDING.md).

Bopo is the local runtime/control shell. Archotraz retains canonical evidence authority in SQLite; Bopo runtime/database state is operational state only.

### Unresolved — do not invent

The following remain explicitly unresolved:

1. **Concrete hostile-code sandbox implementation.**
   The isolation door is required, but its implementation has not been authoritatively selected.

2. **Exact initial thresholds for cell movement and Kitchen promotion.**
   These must be measured/configured rather than fabricated.

3. **Target-machine empirical budgets.**
   Latency, RAM, build time, and operating-cost limits must be measured on the actual environment.

4. **Final calibration for promotion of algorithms out of Psych Ward.**
   Lifecycle is known; exact thresholds are not.

These unresolved bindings do not block implementation through the first real Guard run.

## 16. Change-control rule

Any implementation change that alters:
- canonical evidence ownership;
- production algorithm authority;
- stage ownership;
- Dry Mode capability boundaries;
- the worker contract;
- or the MVP critical path

must explicitly identify the prior rule being changed and the evidence or decision that supersedes it.

Silent architectural drift is not permitted.
