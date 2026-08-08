# Phase 18.2.11.1 — CAP Architecture Assessment

## Purpose

Audit the existing Canonical Asset Profile subsystem before Production Planning. This phase does not redesign persistence or remove legacy functions. It establishes the approved KEEP / REFINE / REPLACE / REMOVE baseline that later Phase 18.2.11 work must implement.

## Governing decision

**Master canonical references are authored externally in ChatGPT.** VSCS is the canonical governance and production-consumption system for those masters: it registers, classifies, validates, approves, locks, versions and supplies them downstream. VSCS must not maintain a competing master-reference authoring workflow.

## Current architecture findings

The existing CAP subsystem already has several strong foundations:

- CAPs are linked to registered asset identities.
- CAPs have lifecycle/version state.
- Structured `CanonicalReference` records support media type, title, file, version, status, approval metadata and locking.
- Reference files have managed-file/provenance infrastructure.
- The CAP editor has a reference gallery, preview and lifecycle controls.
- Technical and semantic evaluation functions exist.
- Production-readiness evaluation exists.

The audit also found architectural overlap and missing production semantics:

1. The CAP model retains a legacy `reference_paths` collection while a structured reference repository already exists. These are competing reference sources.
2. Reference roles are only `Primary`, `Secondary` and `Supplementary`. They express importance, not production viewpoint such as front, rear, port, starboard, top or detail.
3. `production_notes` can mix canonical behavior, constraints, production guidance and story-specific actions.
4. The CAP Manager can generate CAP drafts from manually pasted story context even though Approved Story Intelligence is now the upstream story contract.
5. The CAP UI contains canonical image generation and feedback-regeneration workflows, despite the approved external ChatGPT master-reference workflow.
6. A single production-readiness concept cannot distinguish identity readiness from reference/planning/generation readiness.
7. No category-specific reference coverage contract currently defines what a ship, character, location, vehicle or prop needs.
8. No deterministic downstream reference-selection contract exists for Shot Planning and Prompt Compilation.

## Capability disposition

### KEEP

- XPD/Asset-to-CAP identity linkage.
- CAP lifecycle and versioning.
- Structured canonical reference registry.
- Managed reference files, provenance and integrity metadata.
- Canonical reference gallery and preview.

### REFINE

- Canonical description: retain human-readable prose but add structured canonical facts/invariants.
- Visual identity: formalize visual invariants and completeness semantics.
- Reference lifecycle: add explicit rejection and formalize lock behavior.
- Reference deletion: approved/locked references should archive instead of being destructively deleted.
- Technical image evaluation: retain as optional non-authoritative QC.
- Semantic image evaluation: retain only as advisory compliance checking against approved CAP facts/constraints.

### REPLACE

- Free-form production notes → functional identity + canonical constraints + production guidance.
- Primary/Secondary/Supplementary role model → production reference role/viewpoint taxonomy.
- CAP draft generation from pasted story text → optional assistance sourced from Approved Story Intelligence/XPD facts.
- Single Production Readiness result → separate identity, reference, planning and generation readiness gates.

### REMOVE / DEPRECATE FROM THE CANONICAL WORKFLOW

- Legacy CAP `reference_paths` once migration to structured references is complete.
- `Generate Canonical Images` as a master-reference authoring function.
- `Regenerate from Feedback` as a master-reference authoring function.

The generation implementation may remain temporarily for migration/backward compatibility, but later 18.2.11 phases must remove it from the authoritative CAP workflow and UI. No destructive removal is performed in 18.2.11.1.

## Production-contract gaps to close before Phase 18.3

1. Structured canonical facts/invariants.
2. Functional/behavioral identity independent of a specific story scene.
3. Explicit canonical constraints/prohibited variations.
4. Viewpoint/production reference roles.
5. Category-specific required and optional reference sets.
6. Explicit reference origin/authoring provenance, including ChatGPT master provenance.
7. Deterministic downstream reference-selection API.
8. Separate identity/reference/planning/generation readiness gates.
9. Explicit canonical variant contract.
10. Read-only CAP production projection/API for downstream production systems.

## Production Planning boundary

The intended boundary after Phase 18.2.11 is:

```text
XPD Asset Identity
        ↓
Canonical Asset Profile
        ├─ Canonical facts
        ├─ Visual identity
        ├─ Functional identity
        ├─ Constraints
        ├─ Production guidance
        ├─ Approved typed references
        └─ Readiness gates
        ↓
Read-only CAP Production Contract
        ↓
Production Planning / Shot Planning
```

Scene-specific facts such as current action, camera, lighting, dialogue, emotional state or a one-off story event remain outside the CAP and belong to Story Intelligence / Production Planning / ACPP.

## Multi-reference requirement

CAPs must support multiple references. Later subphases will formalize category-specific role sets. A ship, for example, may use Primary Three-Quarter, Front, Rear, Port, Starboard, Top and optional detail references. A character will use a different role set. The downstream selector must request the smallest appropriate approved reference subset for the planned shot rather than indiscriminately passing every image.

## Acceptance criteria for 18.2.11.1

- Every major existing CAP capability has an explicit architectural disposition.
- Master-reference authoring policy is explicit and testable.
- Structured references are selected as the future single reference source of truth.
- Redundant generation/regeneration functions are identified for removal/deprecation rather than extended.
- Required Production Planning contract gaps are explicitly recorded.
- Assessment is represented in code and unit tests so later phases cannot silently reintroduce rejected architecture.
- No existing CAP data or behavior is destructively migrated in this assessment-only phase.

## Next work

Phase 18.2.11.2 should define and implement the **Canonical Profile Production Contract data model**, including structured facts, functional identity, constraints, production guidance and migration compatibility. The multi-reference taxonomy and readiness implementation should then build on that stable contract.
