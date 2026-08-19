# ADR 0059 — Phase 20.10 Generated Media Technical Validation

## Status

Accepted for implementation validation.

## Context

Phase 20.9 established the authoritative transition from provider outputs to VSCS-owned Generated Media. The next boundary is to determine whether the managed media is technically usable without conflating measurable technical conformance with human creative approval.

Generated Media already owns a project-relative managed file identity, checksum, byte size, production scope, provider execution provenance, technical metadata, and an explicit governance lifecycle. The governance lifecycle permits technically unusable media to become `INVALID` while prohibiting technical automation from granting `APPROVED` authority.

## Decision

Phase 20.10 introduces a provider-neutral technical validation service and an infrastructure-level FFprobe inspector.

The authoritative flow is:

```text
GeneratedMedia
  -> managed file inspection
  -> TechnicalMediaObservation
  -> explicit GeneratedMediaTechnicalRequirements
  -> deterministic TechnicalValidationIssue set
  -> persisted technical_validation.* metadata
  -> preserve current governance state when passed
  -> mark INVALID through existing governance when blocking failures exist
```

### Measurement and policy are separate

`TechnicalMediaInspector` reports measurable facts only. It does not know production policy or governance rules.

`GeneratedMediaTechnicalRequirements` expresses only explicit measurable constraints. Unspecified requirements impose no constraint.

`GeneratedMediaTechnicalValidationService` compares the two and owns deterministic technical findings.

### Managed file authority is re-verified

Every validation re-checks the managed file against Phase 20.9 ingestion authority:

- project-relative managed path,
- SHA-256 checksum when present,
- byte size when present,
- minimum non-empty file size.

A checksum, size, or managed-path mismatch is a blocking technical failure.

### Supported measurable constraints

Phase 20.10 supports explicit checks for:

- extension,
- container format,
- video codec,
- width and height,
- frame rate with explicit tolerance,
- minimum and maximum duration,
- required or forbidden video stream,
- required or forbidden audio stream,
- audio codec,
- audio channel count,
- sample rate,
- minimum byte size.

The design is intentionally extensible so later inspectors may add measurable properties without making FFprobe an application-layer dependency.

### Passing validation never grants approval

A technical pass persists `technical_validation.status=passed` and observed measurements but leaves the existing Generated Media governance state unchanged.

In particular:

```text
GENERATED + technical pass -> GENERATED
UNDER_REVIEW + technical pass -> UNDER_REVIEW
APPROVED + technical pass -> APPROVED
```

No automated transition to `UNDER_REVIEW` or `APPROVED` is permitted.

### Blocking failures use existing INVALID governance

A blocking technical failure invokes the existing `GeneratedMediaGovernanceService.mark_invalid()` transition with the technical validator as the actor and a deterministic reason containing the blocking findings.

This is not a human rejection. `REJECTED` remains a human review outcome.

### Validation evidence is persisted with Generated Media

The existing `GeneratedMedia.technical_metadata` field is the durable Phase 20.10 validation record. Phase 20.10 does not introduce a parallel validation database.

The service replaces only keys under the `technical_validation.` namespace and preserves unrelated technical metadata.

Persisted evidence includes:

- status,
- validator identity,
- validation timestamp,
- checksum and size,
- stream presence,
- observed container/codec/dimensions/frame rate/duration/audio properties when available,
- deterministic indexed findings.

### FFprobe remains infrastructure

`FFprobeGeneratedMediaInspector` resolves only project-relative managed paths under a configured project root, verifies the local file, calculates checksum/size, and invokes an injected `FFprobeRunner`.

`SubprocessFFprobeRunner` is the production implementation and executes the external `ffprobe` binary. Tests inject a deterministic runner and therefore do not require FFmpeg/FFprobe to be installed.

The application service has no FFmpeg/FFprobe dependency.

## Consequences

- Technical validation is deterministic and auditable.
- Human approval authority remains untouched.
- Media tampering after ingestion is detected.
- Provider-specific tooling cannot silently become Generated Media governance authority.
- Validation survives repository restart because evidence is stored inside the authoritative Generated Media document.
- Failure to execute FFprobe is an inspection error, not proof that media is invalid; the caller can distinguish infrastructure failure from measured non-conformance.

## Deliberately deferred

Phase 20.10 does not implement:

- creative or semantic quality assessment,
- human review and approval (20.11),
- versioning/supersession/selection (20.12),
- ProductionTask completion reconciliation (20.13),
- Generated Media UI (20.14),
- automatic derivation of technical requirements from future delivery/mastering profiles,
- advanced loudness, colour-space, HDR, subtitle, GOP, bitrate, or frame-content analysis.
