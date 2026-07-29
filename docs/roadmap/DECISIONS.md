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
