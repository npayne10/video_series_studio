# ADR 0051 — Phase 20.2 Generated Media Persistence

## Status
Accepted for implementation; local validation pending.

## Context

Phase 20.1 established `GeneratedMedia` as the authoritative VSCS record for provider-generated production artifacts. That authority must survive process restart before live provider execution and output ingestion are introduced.

Existing Phase 19 persistence uses project-local, schema-versioned JSON documents with deterministic identity, atomic writes, and explicit application repository boundaries. Generated Media should follow the same persistence conventions rather than introduce a separate storage technology or provider-owned catalog.

## Decision

Phase 20.2 introduces an application-level `GeneratedMediaRepository` protocol, a governance-aware `GeneratedMediaPersistenceService`, and a project-local `JsonGeneratedMediaRepository` infrastructure adapter.

Each stable `media_id` is persisted as one schema-versioned JSON authority document. Saving an updated governance state replaces the same authority document atomically; governance history remains immutable inside the domain object and is persisted in full.

The repository supports deterministic lookup by:

- media identity;
- production;
- episode;
- scene;
- shot;
- ProductionTask identity; and
- provider execution identity.

All list operations return stable `media_id` ordering.

The application persistence service validates Generated Media governance before write and after read. `register()` refuses to replace an existing stable media identity, while `save()` persists a governance-valid update to that identity.

## Storage boundary

Phase 20.2 persists **Generated Media authority metadata**, not media bytes.

`GeneratedMediaFile.relative_path` remains a project-relative reference to the physical artifact. Provider output discovery, file copying/registration into governed media storage, checksum calculation, and output ingestion remain Phase 20.9 responsibilities. Technical media probing remains Phase 20.10.

This preserves the governing rule:

> Providers produce outputs. VSCS owns Generated Media.

Persistence of the VSCS authority record does not imply that a provider output has already been ingested, technically validated, or approved.

## Persistence format

The initial repository schema version is `1.0`.

The persisted record includes:

- stable media identity and media kind;
- production/episode/scene/shot/ProductionTask scope;
- provider execution provenance;
- project-relative file identity;
- optional SHA-256 and file size;
- governance state and complete governance history;
- Generated Media revision;
- technical metadata; and
- creation timestamp.

Writes use a temporary file followed by `os.replace()` to avoid exposing partially written authority documents.

## Consequences

Generated Media authority can now survive VSCS restart independently of provider session state. Later phases can safely build provider execution, ingestion, validation, review, and UI on a durable media authority boundary.

The repository deliberately does not manage provider jobs, queue state, worker state, leases, physical media copying, creative review UI, or version selection policy.

## Deferred

- Phase 20.3 — Provider Execution Contract Modernisation
- Phase 20.4 — Provider Registry & Capability Resolution
- Phase 20.5 — Live ComfyUI Provider Adapter
- Phase 20.7 — Durable Execution Jobs & Attempts
- Phase 20.9 — Generated Media Ingestion
- Phase 20.10 — Generated Media Technical Validation
- Phase 20.11 — Generated Media Review & Approval
- Phase 20.12 — Versioning / Supersession / Selection
- Phase 20.14 — Generated Media UI
