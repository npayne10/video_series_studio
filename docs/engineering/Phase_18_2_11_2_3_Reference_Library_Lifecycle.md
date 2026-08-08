# Phase 18.2.11.2.3 — Reference Library & Lifecycle

## Purpose

Operationalise the Canonical Production Contract reference model without prematurely replacing the existing CanonicalReference database schema or CAP UI.

The structured `CanonicalReference` database record remains responsible for the managed reference file and legacy metadata. A project-local production metadata overlay records the new contract semantics until the dedicated persistence migration phase consolidates storage.

## Storage boundary

Existing structured reference record:

- CAP database identity (`reference_record_id`)
- managed project-relative file path
- media type
- legacy role/status
- title/description/notes
- version
- legacy approval/lock metadata

Production reference library overlay (`.vscs/cap_reference_library.json`):

- stable production `reference_id`
- CAP/asset identity
- reference family
- production viewpoint
- origin/provenance
- MASTER parent relationship
- generator identity for VSCS-derived references
- source MASTER version
- production lifecycle
- approval identity/time
- immutable lifecycle history

This is an intentional migration boundary, not a second permanent reference repository. Later Phase 18.2.11 work may migrate these production fields into consolidated persistence after their semantics are proven.

## MASTER governance

Each CAP may have exactly one active MASTER library entry.

The MASTER:

- uses family `MASTER` and view `MASTER`;
- has origin `CHATGPT_MASTER`;
- has no parent;
- is registered from an existing structured CanonicalReference record;
- cannot be archived while active derived references depend on it.

After the MASTER and all dependent derived references are archived, a later MASTER revision may be registered. Historical MASTER entries remain available when archived entries are requested.

## Derived production references

A VSCS-derived reference:

- cannot use MASTER family/view;
- requires an active MASTER;
- records the MASTER production reference ID as its parent;
- records the generator used;
- records the source MASTER version;
- starts in Candidate lifecycle state;
- remains non-authoritative until human approval/locking.

Derived generation itself remains deferred to Phase 18.2.11.2.5. This phase provides the governance contract that generation will use.

## Lifecycle

The production lifecycle is deliberately separate from the legacy status field:

```text
Register
   ↓
Candidate ── Reject ──> Rejected
   │                       │
   │ Approve               └── Return to Candidate
   ↓
Approved
   │
   │ Lock
   ↓
Locked
```

Archive is an explicit terminal governance action for references being retired from the active production set.

Rules:

- Only Candidate references may be approved.
- Only Approved references may be locked.
- Candidate or Approved references may be rejected.
- Rejected references may return to Candidate.
- Approved references may return to Candidate before the production lifecycle is explicitly Locked.
- Locked references cannot be silently reopened; they require archival/version replacement.
- An active MASTER cannot be archived while active children depend on it.
- Archive history is preserved; hard deletion is not part of the production-library lifecycle.

The existing CanonicalReference service is mirrored where possible so old UI behavior remains compatible during migration.

## Production projection

`ReferenceLibraryService.production_reference()` combines the structured reference file/version with production metadata and returns the `ProductionReference` model introduced in Phase 18.2.11.2.2.

This is the boundary that later CAP Production Projection construction will consume.

## Backward compatibility

No database migration is performed in this phase.

Existing CAPs and structured references continue to work. References acquire production-library semantics only when registered into the new library. The existing CAP editor is intentionally unchanged until Phase 18.2.11.2.9.

## Deferred work

This phase does not implement:

- automatic MASTER registration from New Asset;
- category-specific reference requirements;
- derived image generation;
- generator plugin selection;
- readiness calculation;
- CAP UI redesign;
- database consolidation/migration of overlay fields.

Those responsibilities remain in their approved later subphases.

## Acceptance criteria

- Production reference metadata persists across service/application restart.
- Exactly one active MASTER is enforced for each CAP.
- MASTER origin is ChatGPT and parentage is prohibited.
- VSCS-derived references require and preserve direct MASTER lineage.
- Candidate, Approved, Locked, Rejected and Archived lifecycle semantics are explicit and audited.
- Locked references cannot be silently reopened.
- A MASTER cannot be archived while active derived references depend on it.
- ProductionReference projection combines managed reference file data with production metadata.
- Existing CanonicalReference persistence and current CAP UI remain compatible.
