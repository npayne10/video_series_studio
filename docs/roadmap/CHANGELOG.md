# VSCS Changelog

All notable changes to the Video Series Creation System are recorded here.

The project follows semantic versioning where practical.

## Unreleased

### Added

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

- Phase 20.18.2.2f replaces governance-heavy provider text with bounded cinematic scene/action prompts and keeps reference metadata out of the creative text encoder.
- Phase 20.18.2.2f stops the LTX continuity/reference runtime from prepending reference-role authority prose to series-entry Shot prompts.

### In progress

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
