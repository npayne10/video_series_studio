# VSCS Changelog

All notable changes to the Video Series Creation System are recorded here.

The project follows semantic versioning where practical.

## Unreleased

### Added

- Phase 20.18.2.3.6 Automated Introduction Boundary Synthesis & Span Orchestration: exact preceding-span boundary extraction, Qwen Image Edit canonical-asset insertion, incremental Candidate C span execution, automated structural Introduction Keyframe authority, and final assembled-Shot handoff to human visual QC.
- Phase 20.18.2.3.6 Production Execution now exposes a non-blocking Run Automated Span Orchestration action while retaining Phase 3.5 keyframe/package/assembly controls as explicit manual recovery paths.
- Phase 20.18.2.3.5 Timed Asset Presence authoring bridge: explicit frame-interval editing from governed assets, direct governed ReferencePlan linkage, no prose-based timing inference, and persistence through ProductionPackage authority.
- Phase 20.18.2.3.5 UI, QC and Functional Acceptance: operator-visible timed-span acceptance states, Introduction Keyframe approval controls, Candidate C span acceptance-package generation, exact normalized-span assembly evidence, and human boundary QC.
- Phase 20.18.2.3.5 verifies approved internal-boundary evidence against the actual decoded final frame of the preceding normalized span and checksum-pins both span sources and the final assembled Shot.

- Phase 20.18.2.3.4 Governed Introduction Keyframes: deterministic frame-96 introduction requirements, checksum-pinned human approval, source-boundary continuity evidence, and explicit non-duplication semantics for internal boundaries.
- Phase 20.18.2.3.4 LTX-2.5 per-span provider conditioning: governed/provider frame-count separation, approved Introduction Keyframe binding, Candidate C no-direct-multi-reference policy, and normalized sequential assembly authority.

- Phase 20.18.2.3.3 Timed Canonical Reference Activation: deterministic per-span canonical-reference authority derived from Timed Asset Presence, Internal Render Span topology, and the compiled governed ReferencePlan.
- Phase 20.18.2.3.3 explicit frame-state-reference separation, reference-to-asset ownership validation, source fingerprinting, and fail-closed rejection of unscoped supporting references in dynamic multi-span Shots.

- Phase 20.18.2.3.2 Governed Internal Render Spans: deterministic Shot-internal span topology, exact frame coverage, source/target span linkage, and governed internal-boundary requirements derived from Timed Asset Presence authority.
- Phase 20.18.2.3.2 provider-neutral span IDs, boundary IDs, plan fingerprinting, transition asset sets, and tamper-detecting round-trip validation.

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

- Phase 20.18.2.3.6 dynamic multi-span Candidate C packages declare automated internal orchestration while continuing to prohibit ordinary monolithic Start Production.
- Phase 20.18.2.3.6 distinguishes automated structural Introduction Keyframe authority from final human semantic visual acceptance.
- Phase 20.18.2.3.5 Candidate C can compile dynamic timed-span Shots into acceptance-ready authority while ordinary monolithic Start Production remains fail-closed.
- Phase 20.18.2.3.5 Production Execution disables monolithic Start for dynamic Shots and exposes the governed keyframe/package/assembly/QC workflow without consuming or resetting ProductionTask retry authority.

- Phase 20.18.2.3.4 Production Package compilation now carries Introduction Keyframe requirements into composition and executable package fingerprints.
- Phase 20.18.2.3.4 exposes governed LTX-2.5 span conditioning from Candidate C while keeping the existing monolithic execution path fail-closed until multi-span orchestration is explicitly enabled.

- Phase 20.18.2.3.3 Production Package compilation now carries per-span active/introduced/removed canonical reference IDs into composition and executable package fingerprints.
- Phase 20.18.2.3.3 keeps dynamic provider execution fail-closed after successful reference activation until governed multi-span orchestration and internal-boundary runtime are implemented.

- Phase 20.18.2.3.2 Production Package compilation now derives internal render-span authority from reviewed Timed Asset Presence and includes it in composition/package fingerprints.
- Phase 20.18.2.3.2 keeps multi-span provider execution fail-closed until timed canonical-reference activation and governed span orchestration are implemented.

- Phase 20.18.2.3.1 fails closed when a dynamic timed-presence plan reaches the current monolithic ComfyUI execution path; internal governed render spans are required before in-shot composition changes may execute.

- Phase 20.18.2.2i Candidate C packages include shot-boundary continuity in their executable fingerprint and become STALE when inherited source boundary or source-media checksums change.

- Phase 20.18.2.2h Candidate C Production Packages declare explicit provider audio authority; silent and canonical-dialogue Shots discard provider audio before Generated Media registration.

- Phase 20.18.2.2f replaces governance-heavy provider text with bounded cinematic scene/action prompts and keeps reference metadata out of the creative text encoder.
- Phase 20.18.2.2f stops the LTX continuity/reference runtime from prepending reference-role authority prose to series-entry Shot prompts.

### In progress

- Phase 20.18.2.3.6 local verification and live SHT-002 automated Ros frame-96 orchestration acceptance.
- Phase 20.18.2.3.5 local verification and SHT-002 Ros frame-96 UI/QC/functional acceptance.

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
