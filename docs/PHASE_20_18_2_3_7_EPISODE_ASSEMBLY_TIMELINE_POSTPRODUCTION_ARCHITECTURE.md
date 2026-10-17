# Phase 20.18.2.3.7 — Episode Assembly, Timeline Governance & Automated Post-Production Architecture

**Status:** Proposed architecture baseline for operator review; no implementation authorization
**Scope:** Episodic and standalone video productions; retain recovered SHT-003 unchanged
**Repository:** npayne10/video_series_studio
**Dependency:** VSCS_Video_Production_Workflow_V2.md (active engineering baseline) and Phase_17_6_1_4_Required_VSCS_Capability_Map.md

## 1. Architectural decision and existing-baseline reconciliation

The Story remains the canonical truth. An Episode is an executable Production interpretation, with stable Episode → Sequence → Scene → Shot identities. Approved Generated Media, CAP references, boundaries and QC evidence are immutable inputs; assembly creates *new* governed objects and never rewrites their sources.

Existing workflow v2 describes Dialogue/Lip-sync and QC before Timeline Assembly (steps 17–20); the new operator-approved approach establishes an *initial non-destructive rough-cut timeline before final dialogue timing/lip-sync*, while retaining **Shot technical/visual QC before use in a production-approved assembly**. This is a deliberate proposed revision, **not** a silent change to the active baseline. On approval, issue v2.1 or an amendment with traceability to the earlier phases.

A single-span Shot output may be byte-identical to its normalized video. This is **Shot-level assembly**, not concatenation with previous Shots. Full Episode exports occur downstream.

## 2. End-to-end lifecycle

1. Story/structure/Shot contracts approved (existing VSCS planning).
2. Each Shot: generate → normalize/assemble its own internal spans → verify → register Generated Media → human QC/approve or reject.
3. **Shots Ready for Assembly** (scope can be Episode/Video or selected Scenes): preflight required Shot coverage, approved media, checksums, continuity boundaries and scope membership. A human **Episode / Video Shots Complete** declaration freezes the declared Shot-set revision; it does not complete individual ProductionTasks or force every Shot to be finished. Reopening requires a new revision.
4. **Assembly Workspace** creates an editable, versioned timeline. Select approved Shots, scene markers, reorder, trim, split with references, optional transitions, and inspect adjacent cut continuity. No destructive concatenation during editing. Partial/provisional assembly permits unapproved media only with prominent warnings and blocks production approval.
5. **Rough-cut review** then picture/dialogue timing lock (separate approval). Changes after lock generate a new revision and selectively invalidate dependent work.
6. Generate/import voice performances, align words/phonemes and Shot audio segments against locked timeline timing. Process lip-sync on *individual visible-speaking Shot segments*, produce new governed media derivatives, review and selectively substitute them into the timeline. Do **not** lip-sync a 30-minute concatenation.
7. Audio ambience/Foley/SFX/music, colour matching/grading, VFX, credits/captions, mix and loudness QA on timeline-derived tasks. Re-lock after affected changes; invalidate only dependent segments when possible.
8. Produce review exports on demand. Final mastering/export only when approved timeline revision, derivatives, audio mix and human QC pass. Archive manifests/checksums.

## 3. Lifecycle state contracts (proposed; never override existing state enums)

- Shot Production Completion Declaration: DRAFT → READY_FOR_REVIEW → DECLARED_COMPLETE → SUPERSEDED (new revision). BLOCKED is derived readiness, not silently persisted as approval.
- Assembly Revision: DRAFT → PROVISIONAL_REVIEW → PICTURE_LOCKED → POST_PRODUCTION → FINAL_QC_REQUIRED → APPROVED → MASTERED; SUPERSEDED links revisions.
- Post-production Task: PLANNED → READY → RUNNING → GENERATED → UNDER_REVIEW → ACCEPTED / REJECTED / BLOCKED. No automatic human approvals.
- Distinguish Generated Media state (GENERATED, UNDER_REVIEW, APPROVED, etc.) from Assembly state and ProductionTask completion state. No cross-object approval side effects.

## 4. Proposed immutable data contracts (v1)

**AssemblyScope:** production_id, episode_id or standalone_video_id, declared_shot_set_revision, scope_kind, owner, story/structure fingerprint.

**ShotSelection:** scene_id, shot_id, selected_generated_media_id, media_revision, file_checksum, approval_evidence_ref, source_in_frame, source_out_frame (half-open), sequence_index, optional transition specification, continuity/boundary evidence references.

**AssemblyTimelineRevision:** assembly_id, revision_id, scope, ordered video tracks, scene/sequence markers, dialogue tracks, ambience/music/SFX tracks, titles/captions, frame-rate/timebase, aspect/resolution targets, derived runtime, selection fingerprints, dependencies, reviewer, state, predecessor_revision, created timestamp, manifest SHA-256.

**PostProductionJob:** id, assembly_revision, selected media/segment, provider/model/config, asset and character identity, approved voice/audio ID, start/end frame and sample alignment, dependency hashes, estimated cost, retry/approval policy, output derivative ID, QC state.

**MasterDeliverable:** master_id, assembly_revision, locked post-production dependencies, codec/container, fps, resolution, aspect, channel layout, target loudness, file SHA-256, human QC/approval, publication target.

Persist under project-local versioned JSON stores with atomic replace and checksum verification. Paths are implementation proposals, not declarations of existing storage conventions.

## 5. Mandatory invariants

- Never mutate original approved Shot media, existing Generated Media records, SHT-002 boundary, or recovered SHT-003 output.
- All timeline selections resolve exact media revisions and verified files; stable Shot IDs are not sufficient on their own.
- Continuity means inherited visual/environment/camera/audio context; it does **not** mean append all earlier Shots inside each new Shot.
- Trim/edit decisions are frame-accurate (24 fps production default), dialogue mapping must be sample accurate or explicitly timebase-converted; transitions affect overlap and duration deterministically.
- Scene boundaries mark narrative changes; a continuous episode is an export/playback property, not evidence every Scene must have continuous visual action.
- Production-approved assembly requires APPROVED Shot media; provisional previews are explicitly watermarked/flagged and cannot be mastered.
- Lip-sync after rough-cut timing lock, before final delivery; input must reference audio performance, speaker, selected media, time range and stable character identity.
- If edit timing changes, recompute impacted dependency hashes and invalidate only affected audio/lip-sync/render tasks.
- Assembly and recovery must be resumable from verified checkpoints; no auto-rerender, duplicate adoption or silent approval.
- Three provider modes remain supported in architecture: internal only, hybrid and external; post-production jobs must use provider-neutral contracts and zero-cost/local-first profiles when available.

## 6. UI workspace blueprint

**Shot Readiness/Completion:** Episode scope selector; required/approved/missing/rejected/provisional counts; Shot/scene table; blocking reasons; 'Mark Shots Ready for Assembly'; human 'Episode / Video Shots Complete'; revision history and controlled reopen.

**Assembly Workspace:** source bin of Generated Media with thumbnail, Shot/Scene, duration, media state, checksum, recovery warning and QC link; Shot selection/version pinning; nonlinear editable multitrack timeline; scene markers; frame-accurate trims; continuity viewer (prior close vs next open); duration roll-up; draft save; assembly preview; deliberate picture/dialogue lock. Keep provenance limitation visible for historical SHT-003.

**Post-Production Workspace:** derived task queue, dialogue alignment/voice, visible-speaker detection review, shot-level lip-sync, audio layers, grading/VFX/captions, dependency invalidation dashboard, per-task human QC and reassembly preview.

**Mastering:** technical/human QA matrix, explicit master approval, export presets, checksum/manifest and archive.

## 7. Incremental implementation plan and gates

- **20.18.2.3.7.1 — Repository audit & workflow amendment:** inventory existing Shot/Generated Media/Audio/Timeline UI and persistence; approve mapping and gap list. No runtime change.
- **.7.2 — Data contracts & validators:** versioned schema, selection fingerprinting, coverage/readiness and transition arithmetic; unit tests and fail-closed corruption tests.
- **.7.3 — Assembly scope and completion declaration:** read-only preflight, explicit human declaration, revision and reopen handling; UI tests.
- **.7.4 — Assembly Workspace MVP:** source browser, selectable ordered approved Shot list, non-destructive timeline and provisional preview; no lip-sync or final export initially.
- **.7.5 — Timeline locking and post-production DAG:** approved dialogue timing and invalidation contracts; human-review checkpoints.
- **.7.6 — Shot-level lip-sync pipeline:** voice/character scope, provider-neutral local-first adapter, derivative media registration, QC.
- **.7.7 — Audio/colour/VFX/captions and final master:** task orchestration, deterministic export, QA and delivery.
- **.7.8 — End-to-end episode acceptance:** mixed continuous/new Scene, partial revisions, selected replacement, multi-track sync, interrupt/restart, costs, validation and human master sign-off.

Each development stage requires direct GitHub code change, commit, local PowerShell fetch/pull instructions, ruff check/format, mypy, focused + full pytest, UI steps with expected outcomes, no claimed passes until observed. Ruff-only changes mirrored into GitHub; no separate local commit/push unless user modifies code.

## 8. SHT-003 baseline disposition

SHT-003 `GM-H3-006641D56A556A97DA398A3F` is historically recovered, GENERATED, pending visual QC, with original compiled package unavailable. Do not count as approved production media. Preserve SHA-256 `9457f998dcf4f073b7440e9d783bce5ad80a9912cf5b6c5cb50bd00396f35430`, 240 frames @24fps. SHT-002 approved boundary and existing approvals remain unchanged. It may appear in a provisional Assembly source bin with provenance warning after the relevant UI exists, never final-master input until separate QC/approval policy is satisfied.

## 9. Architecture acceptance checklist

Before implementation: approve workflow amendment relative to v2; confirm declared scope/shot list; demonstrate state-transition legality; version-pinned source selections; non-destructive trim arithmetic; provisional vs final QC barriers; timeline-driven shot-level lip-sync; deterministic invalidation; internal/hybrid/external provider policy; restart recovery; UI navigation; zero unapproved Shot promotion; regression evidence. Architecture approval is **not** permission to generate, approve, concatenate or export SHT-003.
