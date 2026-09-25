# VSCS Architectural Decision Log

This document records significant architectural and engineering decisions for the Video Series Creation System.

Each decision should be stable, traceable, and linked to the milestone or pull request that implemented it.

## Decision status

- Proposed
- Accepted
- Superseded
- Rejected
- Deprecated

---

## ADR-001 — Repository-first development

**Status:** Accepted  
**Date:** 2026-07-29

### Context

VSCS has grown into a multi-module production software platform. Large code listings exchanged only through chat create integration, versioning, and verification risks.

### Decision

New development will be implemented directly in the GitHub repository. The project owner will pull each milestone into the local repository and run the supplied PowerShell test commands before approval.

### Consequences

- GitHub becomes the shared source of truth.
- Every milestone must identify its commit or pull request.
- Local testing remains mandatory before approval.
- Chat responses summarise changes and provide pull and test commands.

---

## ADR-002 — Gated milestone lifecycle

**Status:** Accepted  
**Date:** 2026-07-29

### Context

Parallel changes made before previous work is verified can create difficult-to-isolate regressions.

### Decision

No new milestone begins until the previous milestone passes focused tests, the regression suite, and owner approval, unless parallel work is explicitly authorised.

### Consequences

- Each approved commit becomes a known-good baseline.
- Defect localisation is simpler.
- Development may proceed more slowly, but with lower integration risk.

---

## ADR-003 — Modular CAR validator architecture

**Status:** Accepted  
**Date:** 2026-07-29

### Context

The original validator had grown into a large monolithic module containing visual, configuration, behaviour, health, and reporting concerns.

### Decision

The CAR validator is organised as a package with separate modules for orchestration, models, base functionality, visual validation, configuration validation, behaviour validation, health scoring, and reports.

Target package:

```text
src/vscs/application/car/validator/
    __init__.py
    base.py
    behaviour.py
    configuration.py
    constants.py
    health.py
    models.py
    reports.py
    validator.py
    visual.py
```

### Consequences

- Behaviour Part 4B2 will be implemented incrementally in `behaviour.py` and supporting modules where justified.
- Public imports should remain stable where practical.
- The legacy implementation must not be deleted until feature parity and regression coverage are confirmed.

---

## ADR-004 — Semantic versioning

**Status:** Accepted  
**Date:** 2026-07-29

### Context

VSCS requires predictable release identifiers across development, release candidates, and production releases.

### Decision

Use semantic versioning where practical:

```text
MAJOR.MINOR.PATCH
```

Release candidates use:

```text
v1.0.0-rc.N
```

The first production release is:

```text
v1.0.0
```

### Consequences

- Breaking public-interface changes require explicit version consideration.
- Changelog and release notes must identify version impact.

---

## ADR-005 — Xorix as the reference UAT production

**Status:** Accepted  
**Date:** 2026-07-29

### Context

VSCS requires a realistic end-to-end reference project that exercises story planning, canonical assets, prompt compilation, production packaging, and quality-control preparation.

### Decision

The Xorix Streaming Series will serve as the mandatory end-to-end reference production for UAT-07.

### Consequences

- Generic framework architecture remains mandatory.
- Xorix-specific assumptions must not be embedded in reusable core modules.
- UAT evidence must demonstrate that the generic system can process the Xorix project successfully.

---

## ADR-006 — Governed provider-ready reference roles

**Status:** Accepted  
**Date:** 2026-08-27

### Context

Phase 20.18 validation demonstrated that an approved canonical reference can still be unsuitable for direct video generation. A portrait reference supplied to a landscape video workflow forced provider preprocessing to crop or extrapolate unseen content, materially degrading subject identity and design continuity. Complex shots may also require several independent sources of visual authority: composition, character identity, environment, furniture, props, continuity state, and start/end targets.

### Decision

VSCS will distinguish canonical master authority from provider-ready reference suitability. Shot references must be explicitly role-bound, suitability-validated against the target generation profile, and mapped to provider workflow inputs through provider-edge capability declarations.

Required shot content must be visible in at least one required governed reference. The system must not silently depend on a provider to invent unseen canonical content. Multi-reference plans remain provider-neutral in the VSCS core; provider-specific binding limits and fallback strategies remain at the provider/infrastructure edge.

### Alternatives considered

- Treat every approved canonical image as directly provider-ready. Rejected because approval does not guarantee suitable framing, aspect ratio, dimensions, or asset coverage.
- Store only one start image per shot. Rejected because complex multi-subject production requires multiple independent sources of canonical authority.
- Embed provider-specific reference fields directly into the core production package. Rejected because it would violate provider neutrality and make future providers harder to integrate.

### Consequences

- Production packages may carry a governed multi-reference plan.
- Provider-ready derivatives remain traceable to canonical masters.
- Required aspect/framing/coverage failures can block provider execution before generation.
- Providers may bind references directly or use an explicit governed fallback, but required authority may not be silently discarded.
- Provider adapters must declare their supported reference roles and reference-count constraints.

---

## ADR-007 — Automated internal asset introduction with exception-based human recovery

**Status:** Accepted  
**Date:** 2026-09-25

### Context

Phase 20.18.2.3.5 proved frame-exact timed asset introduction by requiring a human to
provide both the preceding internal-boundary frame and the target Introduction Keyframe.
That is safe for functional acceptance but does not scale to automated episode production:
every mid-Shot character, ship, planet, location, prop or technology introduction would
create repetitive manual image work.

VSCS already owns the information needed to produce those technical artifacts: exact
internal span topology, canonical references, source-boundary frame indices, provider
conditioning requirements and final visual-QC authority.

### Decision

Normal dynamic-Shot production will use automated internal-boundary orchestration.

VSCS will render the preceding governed span, extract its exact final normalized frame,
and either use validated provider-native timed reference injection or synthesize the
target Introduction Keyframe automatically from that source frame and governed canonical
references. The next span then executes from that machine-produced structural keyframe.

Human image preparation is not part of the normal path. Manual Introduction Keyframe,
span-package and assembly controls remain explicit recovery mechanisms.

Automated structural checks may authorize provider conditioning, but final semantic visual
acceptance remains a separate human QC gate until a governed vision-capable evaluator is
introduced.

### Alternatives considered

- Require two manually created images at every internal boundary. Rejected because it
  defeats production automation and scales poorly across episodes.
- Remove internal span boundaries and rely on provider prose alone. Rejected because it
  abandons frame-exact timed presence and reference authority.
- Treat automatically generated images as fully human-approved semantic evidence.
  Rejected because checksum/geometry validation cannot prove identity, presence or visual
  continuity.

### Consequences

- Dynamic Shots remain one editorial ProductionTask rather than multiple retry-consuming
  child tasks.
- Exact preceding boundary frames are generated from actual provider output rather than
  prepared by the operator.
- Current LTX-2.5 Candidate C uses Qwen Image Edit 2511 for automatic introduction-frame
  synthesis.
- Future providers may bypass synthesis when direct timed-reference injection has been
  explicitly validated.
- Final visual QC remains human and exception/recovery controls remain available.
- Automation failures fail closed without resetting ProductionTask retry authority.

---

## ADR template

Use this template for future decisions:

```markdown
## ADR-NNN — Decision title

**Status:** Proposed  
**Date:** YYYY-MM-DD

### Context

Describe the problem, constraints, and relevant forces.

### Decision

State the selected approach.

### Alternatives considered

List meaningful alternatives and why they were not selected.

### Consequences

Describe positive effects, trade-offs, risks, and follow-up work.
```
