# ADR 0058: Phase 20.9 Generated Media Ingestion

- Status: Accepted for implementation; local validation pending
- Date: 2026-08-18
- Phase: 20.9 — Generated Media Ingestion

## Context

Phases 20.5–20.8 established live provider execution, queue-authorised submission, durable execution identity, and provider monitoring/recovery. Provider execution currently yields `RenderOutput` / `ProviderExecutionOutput` descriptors. Those objects are execution artifacts, not authoritative production media.

Phase 20.1 established `GeneratedMedia` as the VSCS-owned authority for generated production artifacts. Phase 20.2 established durable Generated Media metadata persistence. A controlled ingestion boundary is therefore required between completed provider outputs and authoritative Generated Media.

## Decision

### Providers produce outputs; VSCS ingests and owns media

A provider output becomes `GeneratedMedia` only through `GeneratedMediaIngestionService`.

Ingestion requires:

1. a durable provider execution in `COMPLETED` state;
2. a matching `ProductionTask` with the same production/task identity and unchanged authority fingerprint;
3. one or more typed `ProviderExecutionOutput` descriptors;
4. a configured `GeneratedMediaFileStore` capable of copying provider output bytes into VSCS-managed project storage; and
5. the existing `GeneratedMediaPersistenceService`.

### Managed file ownership

The local file-store adapter copies provider output bytes from a configured provider-output root to a project-relative managed path:

`generated_media/<production>/<episode>/<task>/<media-id>.<extension>`

The provider source file remains untouched.

Before authoritative metadata registration, the copied file is verified by SHA-256 and byte size. Existing managed files are reusable only when their content matches exactly. Different content at an existing authoritative destination is an error and is never overwritten silently.

### Deterministic and idempotent identity

Generated Media identity is deterministic from the VSCS execution identity plus provider-output identity. Re-ingesting the same execution/output pair returns the existing Generated Media record and does not copy the file again.

Input output tuples are processed in deterministic `output_id` order.

### Output-kind classification

Provider/render output kinds are explicitly mapped to provider-neutral `GeneratedMediaKind` values. Examples:

- `preview_video`, `production_video`, `lip_sync_video` → `VIDEO`
- `reference_frame` → `IMAGE`
- `image_sequence` → `IMAGE_SEQUENCE`
- dialogue/music/effects output kinds → `AUDIO`
- `qc_report` → `REPORT`
- metadata output → `METADATA`

Unknown output kinds are rejected rather than guessed.

### Provenance

Generated Media provenance captures:

- durable `execution_id`;
- provider and provider-job identity;
- render request and workflow identity;
- source render-output identity when available;
- queue-entry and worker identity;
- attempt number;
- resource identity;
- production authority fingerprint;
- provider-output identity and source relative path; and
- provider/output metadata as namespaced provenance attributes.

Provider and workflow details remain provenance only and do not control Generated Media governance.

### Governance state

Newly ingested media always starts in `GeneratedMediaState.GENERATED`. Ingestion does not technically validate, approve, reject, select, supersede, or complete the owning ProductionTask.

## Consequences

- Completed provider outputs can now enter the authoritative VSCS media domain.
- Provider output locations are no longer the authoritative production-media location.
- File integrity is captured immediately through checksum and size metadata.
- Repeated ingestion is safe and deterministic.
- Provider output classification is explicit and provider-neutral.
- Generated Media remains subject to later technical validation and human governance.

## Deferred

Phase 20.9 does not implement:

- media decoding or technical validation (Phase 20.10);
- human review/approval (Phase 20.11);
- version selection/supersession policy (Phase 20.12);
- ProductionTask completion reconciliation (Phase 20.13);
- Generated Media UI (Phase 20.14);
- execution UI (Phase 20.15); or
- automatic startup/restart orchestration (Phase 20.16).
