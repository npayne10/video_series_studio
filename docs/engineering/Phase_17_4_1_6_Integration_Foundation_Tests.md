# Phase 17.4.1.6 — Integration and Foundation Tests

## Purpose

This phase closes the Prompt Graph Foundation by proving that the individual services introduced in Phases 17.4.1.1 through 17.4.1.5 operate as one deterministic production subsystem.

## Integrated pipeline

The verified flow is:

```text
PromptGraphBuildContext
→ PromptGraphResolver
→ PromptGraphBuilder
→ PromptGraphValidator
→ PromptGraphCompiler
→ PromptPackage
→ PromptGraphSnapshotService
→ PromptGraphDiffer
```

All services are resolved through the shared VSCS application dependency graph.

## Verified production behavior

The integration tests verify that:

- Story and production knowledge sources are assembled in stable order.
- Canonical character, ship and location identities survive graph construction.
- Approved reference-image identities survive compilation.
- Full production descriptions are retained without summarization.
- Critical visual details such as the Iron Horizon's four rear fusion engines and controlled blue-white engine trails remain in the positive prompt.
- Continuity instructions remain a dedicated structured prompt section.
- Dialogue remains a dedicated structured prompt section.
- Restrictions and negative constraints are excluded from the positive prompt and included in the negative prompt.
- Repeated builds from unchanged source data produce identical graph dictionaries.
- Validation determines whether the graph is production-ready.
- Compilation provenance uses the same graph checksum as the immutable snapshot.
- Snapshot history preserves ordered graph revisions.
- Graph and prompt-package differences expose changed continuity and dialogue.
- Continuity-related differences are explicitly marked as continuity-sensitive.
- Missing canonical resources prevent compilation before renderer submission.

## Test matrix

The primary integration suite is:

```text
tests/integration/test_prompt_graph_foundation_integration.py
```

It contains three end-to-end scenarios.

### Complete production pipeline

Builds a production-quality Xorix shot containing:

- Visual intent
- Canonical bridge location
- Canonical Iron Horizon ship definition
- Canonical Commander James Spence character definition
- Camera
- Lighting
- Continuity
- Dialogue
- Renderer profile
- Quality profile
- Restrictions
- Negative prompt constraints

The graph is validated, compiled and snapshotted. Prompt contents, canonical resources, structured sections, reproducibility and provenance are verified.

### Revision and differencing

Builds and compiles two revisions of the same shot. The second revision changes continuity and dialogue. Both graph-level and prompt-package-level reports must identify those changes, and the continuity changes must be marked as continuity-sensitive.

### Failure isolation

Compiles a valid graph against an incomplete canonical resource inventory. Compilation must stop with a structured validation failure before any renderer or ComfyUI operation can begin.

## Deliberate exclusions

Phase 17.4.1 does not yet include:

- Renderer-specific prompt profiles
- Prompt-preview user interface
- Batch compilation
- Prompt optimization or shortening
- Live ComfyUI submission
- Persistence-backed PromptGraphResolver adapters
- Production workspace integration

These are intentionally deferred to later Phase 17.4 increments.

## Readiness decision

The Prompt Graph Foundation is ready to be frozen when the complete Ruff and pytest suites pass in the target Windows and PySide6 environment.

The completed foundation provides:

- Immutable renderer-neutral production knowledge
- Deterministic graph construction
- Production-readiness validation
- Structured prompt compilation
- Canonical asset and reference traceability
- Snapshot history and reproducibility
- Graph and prompt-package differencing
- Continuity-sensitive change detection

The next planned phase is **17.4.2 — Renderer Profiles and Prompt Preview**.
