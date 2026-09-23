# VSCS Changelog

All notable changes to the Video Series Creation System are recorded here.

The project follows semantic versioning where practical.

## Unreleased

### Added

- Phase 20.18.2.3.1 Timed Asset Presence Model: provider-neutral frame-exact asset intervals, deterministic identities/fingerprints, explicit introduction/removal events, and governed asset-reference linkage.
- Phase 20.18.2.3.1 Production Package / UPD / execution-package propagation for timed asset presence authority, including exact change-frame derivation and timing validation.

- Phase 20.18.2.2i governed Shot Boundary Keyframes: explicit human publication of the exact final governed frame from APPROVED Generated Media, checksum-pinned source provenance, explicit continuity modes, and Candidate C inherited-opening authority.
- Phase 20.18.2.2i Production Execution visibility for opening/closing boundary state and fail-closed closing-boundary publication.

- Phase 20.18.2.2h governed provider-audio policy and fail-closed pre-ingestion audio governance for joint audio/video providers.
- Phase 20.18.2.2h provenance records for discarded/preserved provider audio and stream-copy video normalization.

- Phase 20.18.2.2g LTX-2.5 governed Shot Composition Keyframe authority with checksum-pinned human approval.
- Phase 20.18.2.2g Candidate C manual I2V workflow derived from the pinned official Lightricks LTX-2.5 single-stage I2V workflow.

- Phase 20.18.2.2f controlled provider-video A/B/C rebaseline contract, with LTX-2.5 governed-keyframe I2V as the preferred fail-closed Candidate C target.
- Phase 20.18.2.2f motion-only prompt output for future governed-keyframe image-to-video workflows.

- VSCS v1 development governance documents
- Master roadmap
- Release plan
- Test plan
- Milestone tracker
- Architectural decision log
- Phase 12.1.1-4B2-1A prompt package discovery
- Structured prompt package inventory and discovery statistics
- Diagnostics for missing directories, missing README files, missing or multiple manifests, empty directories, and unexpected directories
- Focused unit tests for valid, incomplete, ambiguous, and ignored prompt package entries

### Changed

- Phase 20.18.2.3.1 fails closed when a dynamic timed-presence plan reaches the current monolithic ComfyUI execution path; internal governed render spans are required before in-shot composition changes may execute.

- Phase 20.18.2.2i Candidate C packages include shot-boundary continuity in their executable fingerprint and become STALE when inherited source boundary or source-media checksums change.

- Phase 20.18.2.2h Candidate C Production Packages declare explicit provider audio authority; silent and canonical-dialogue Shots discard provider audio before Generated Media registration.

- Phase 20.18.2.2f replaces governance-heavy provider text with bounded cinematic scene/action prompts and keeps reference metadata out of the creative text encoder.
- Phase 20.18.2.2f stops the LTX continuity/reference runtime from prepending reference-role authority prose to series-entry Shot prompts.

### In progress

- Phase 20.18.2.3.1 local verification and Ros frame-96 timed-presence model acceptance.

- Phase 20.18.2.2g provider deployment assurance and live Candidate C SHT-001 acceptance.

- Phase 20.18.2.2f Candidate A automated and live SHT-001 acceptance; Candidate B/C remain fail-closed until governed-keyframe workflows are installed and validated.
- Local verification and owner approval for Phase 12.1.1-4B2-1A

## v0.11.10.1

### Added

- CAR Migrator v2
- Asset classification
- Repository migration support

## Change entry format

Use the following headings for future entries:

- Added
- Changed
- Deprecated
- Removed
- Fixed
- Security

Each milestone entry should include its phase identifier and the related commit or pull request where available.
