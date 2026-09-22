# VSCS Changelog

All notable changes to the Video Series Creation System are recorded here.

The project follows semantic versioning where practical.

## Unreleased

### Added

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

- Phase 20.18.2.2h Candidate C Production Packages declare explicit provider audio authority; silent and canonical-dialogue Shots discard provider audio before Generated Media registration.

- Phase 20.18.2.2f replaces governance-heavy provider text with bounded cinematic scene/action prompts and keeps reference metadata out of the creative text encoder.
- Phase 20.18.2.2f stops the LTX continuity/reference runtime from prepending reference-role authority prose to series-entry Shot prompts.

### In progress

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
