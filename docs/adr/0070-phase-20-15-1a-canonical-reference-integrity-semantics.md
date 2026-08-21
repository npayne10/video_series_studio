# ADR 0070 — Phase 20.15.1a Canonical Reference Integrity Semantics

## Status

Accepted for Phase 20.15.1a corrective implementation.

## Context

VSCS historically exposed a field named `checksum` on resolved canonical references. In the current Asset Resolution path that value is produced by `stable_model_checksum(reference)` and therefore fingerprints the CanonicalReference metadata/model. It is not the SHA-256 of the referenced PNG/JPG bytes.

Phase 20.15.1a initially interpreted that legacy value as a physical file checksum and compared it with the SHA-256 of the resolved canonical image. This caused valid canonical assets to be rejected even when the correct file path was resolved.

The two identities serve different governance purposes and must not be conflated.

## Decision

VSCS formally distinguishes:

- `reference_fingerprint`: deterministic fingerprint of CanonicalReference authority/metadata. It participates in authority and dependency change detection.
- `file_checksum`: SHA-256 of the physical canonical reference file bytes. It participates in provider-ready file-integrity validation.

The legacy `checksum` field on canonical-reference production data is interpreted as `reference_fingerprint` for backward compatibility. It must never be compared with physical file bytes.

Asset Resolution calculates both values when the physical file is available. Asset Compiler propagates both values into Production Package authority. Provider-ready resolution validates only an explicitly supplied `file_checksum` against the physical file.

For legacy Production Packages that contain only `checksum`, provider-ready resolution preserves that value as `reference_fingerprint`, calculates the current physical `file_checksum`, records that checksum in the provider-ready package, and does not falsely reject the package by comparing unlike identities.

## Consequences

- Existing projects remain readable without rewriting historical authority.
- New or re-resolved production authority can carry both identities explicitly.
- Physical canonical-file replacement can be detected once a governed `file_checksum` is present.
- Metadata changes remain independently detectable through `reference_fingerprint`.
- Help documentation can describe separate workflows for canonical authority resolution and physical reference integrity.
- The generic provider boundary remains production-neutral; providers consume resolved references and their explicit integrity metadata rather than inferring checksum semantics.
