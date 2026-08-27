# VSCS Architecture vNext — Authoritative Development Roadmap

**Project:** Video Series Creation System (VSCS)  
**Roadmap Status:** ADOPTED DEVELOPMENT BASELINE  
**Adopted:** 2026-08-27  
**Scope:** Post-rationalisation development path from live production through product completion  
**Supersedes for forward planning:** the older high-level Phase 20–25 roadmap where numbering or scope conflicts  

---

## 1. Purpose

This document records the approved post-rationalisation VSCS development roadmap and is the authoritative forward-planning reference for development sequencing through product completion.

The roadmap is based on the VSCS Architecture & Capability Rationalisation review. It preserves the core development rule that production architecture must be proven before large-scale UX consolidation or legacy retirement.

Implementation may introduce corrective or capability-validation subphases inside a major phase where evidence requires them. Such subphases extend the roadmap without changing the major architectural dependency order defined here.

---

## 2. Governing Development Priorities

Development priority is:

1. **Make production executable** — ProductionTask, ProductionGraph, Scheduler, Queue, Resources.
2. **Make providers real** — provider execution, ComfyUI, GeneratedMedia, monitoring.
3. **Make production self-correcting** — QA, findings, repair and selective regeneration.
4. **Complete audiovisual production** — voice, TTS, lip-sync, ambience, SFX, music and audio mix.
5. **Finish the Episode** — post-production, assembly, mastering and delivery.
6. **Simplify the product** — dashboard, issues, workspaces and legacy retirement.

The architectural dependency chain is:

```text
ProductionTask
    ↓
ProductionGraph
    ↓
Scheduler
    ↓
ProductionQueue
    ↓
Provider Execution
    ↓
GeneratedMedia
    ↓
QA
    ↓
Repair
    ↓
Audio / Post
    ↓
Assembly
    ↓
Master
```

Therefore:

- QA must not precede GeneratedMedia.
- Repair must not precede QA.
- Post-production must not precede controlled GeneratedMedia selection.
- Mastering must not precede Episode approval.

---

# 3. Phase 19.6 — Production Scheduling & Orchestration

Phase 19.6 establishes the runtime foundation for everything that follows.

### 19.6.1 — ProductionTask Domain & Governance
### 19.6.2 — ProductionTask Compilation
### 19.6.3 — Production Pipeline Stage Modernisation
### 19.6.4 — ProductionGraph Integration
### 19.6.5 — Production Resource & Capability Model
### 19.6.6 — Production Scheduler
### 19.6.7 — ProductionSchedule Persistence & Review
### 19.6.8 — ProductionQueue Generalisation
### 19.6.9 — Worker, Claim, Lease & Retry Integration
### 19.6.10 — Scheduling Monitoring & Recovery
### 19.6.11 — Production Scheduling UI
### 19.6.12 — Production Readiness Integration
### 19.6.13 — Integration & Functional Acceptance

Phase 19.6 must not attempt to implement full live provider rendering, full QA, lip-sync, TTS, music, post-production, AI scheduling, complete UI rationalisation, wholesale legacy removal, or cloud/distributed rendering.

---

# 4. Phase 20 — Provider Execution & Generated Media

**Objective:** Execute actual production tasks and register their resulting media under VSCS authority.

### 20.1 — Provider Capability Registry

Formalise provider capabilities such as VIDEO_GENERATION, IMAGE_GENERATION, VOICE_GENERATION, LIP_SYNC, TRANSCODE and ASSEMBLY. Providers advertise capabilities; schedulers select compatible resources.

### 20.2 — Live ComfyUI Connectivity

Extend the existing ComfyUI adapter rather than replacing it. Required operations include health, submit, monitor, cancel, retrieve_outputs and diagnostics.

### 20.3 — PromptGraph → ProductionTask Integration

Formalise the execution-derived chain from ProductionTask to PromptGraph to Provider Compiler while retaining reusable graph-builder, resolver, compiler, optimisation, snapshot and batch infrastructure.

### 20.4 — Provider Compilation Orchestration

Establish the definitive execution chain:

```text
ProductionTask
→ PromptGraph
→ ProviderCompiler
→ RenderRequest
→ WorkflowCompiler
→ Adapter
```

### 20.5 — GeneratedMedia Registry

Introduce GeneratedMedia, GeneratedMediaStatus, GeneratedMediaRepository and GeneratedMediaService. No generated output may remain an anonymous filesystem artifact.

### 20.6 — Take / Candidate Management

Support governed takes with lifecycle states such as CANDIDATE, REJECTED, APPROVED, STALE and SUPERSEDED.

### 20.7 — Automated Output Registration

Provider outputs automatically become GeneratedMedia entries carrying provider, job, task, authority revision, workflow revision, technical metadata and file location.

### 20.8 — Frame / Reference Extraction

Automatically extract start frames, closing frames, continuity frames and reference crops from generated media for downstream tasks.

### 20.9 — Live Production Monitoring

Production workspace expands to Schedule, Queue, Running and Outputs.

### 20.10 — Integration & Functional Acceptance

Prove a real Shot can travel from UPD through ProductionTask to live ComfyUI, output retrieval and GeneratedMedia registration. This is the first point where VSCS itself truly produces media end-to-end.

### Phase 20 implementation refinements

Evidence-driven subphases may be added beneath Phase 20 without changing the Phase 20 architectural objective. Current examples include provider capability validation and provider-ready reference governance. These refinements remain subordinate to the Phase 20 objective and must ultimately converge into Phase 20 integration and functional acceptance.

---

# 5. Phase 21 — Production Quality & Repair

**Objective:** Generate → inspect → diagnose → repair → regenerate → approve.

### 21.1 — QualityFinding Domain
Create QualityFinding, QualitySeverity, QualityCategory and QualityEvidence.

### 21.2 — Technical Media QA
Deterministic checks for file integrity, duration, resolution, fps, frames, codec, audio presence, black frames and frozen frames.

### 21.3 — Visual QA
Multimodal evaluation for identity, costume, location, ships, props, composition and visual artifacts.

### 21.4 — Production Intent QA
Compare outputs against UPD requirements for characters, action, camera, lighting, environment and story beat.

### 21.5 — Continuity QA
Compare previous approved output, planned continuity, current output and next-shot requirement.

### 21.6 — Observed Production State
Approved Shot outputs contribute observed opening and closing state for downstream generation.

### 21.7 — RepairAction Domain
Introduce RETRY, RECOMPILE, REGENERATE, REPROCESS, RERUN_LIPSYNC and HUMAN_REVIEW.

### 21.8 — PRE/CIEE Migration
Migrate useful PRE and CIEE logic into modern Quality/Repair services, then begin deprecating those standalone subsystem identities.

### 21.9 — Automated Repair Loop
Support QA failure → diagnosis → smallest affected task → repair task → rerun → QA.

### 21.10 — Quality Workspace
Quality workspace: Overview, Shot QA, Continuity and Repairs.

### 21.11 — Issues & Decisions Foundation
Begin unifying QA failures, provider failures, canonical issues and planning issues under one operator issue model.

### 21.12 — Integration & Functional Acceptance
Prove one failed Shot can enter a governed repair loop and return as an approved candidate.

---

# 6. Phase 22 — Audio & Performance Production

The audio chain uses the same ProductionTask architecture.

### 22.1 — Canonical Voice Profiles
Expand VoiceProfileRegistry into persistent canonical voice identity.

### 22.2 — Dialogue Task Compilation
Convert UPD dialogue into VOICE_GENERATION tasks.

### 22.3 — TTS Provider Adapter
Support the selected primary TTS engine through the provider capability architecture.

### 22.4 — Pronunciation & Performance Profiles
Support accent, pace, pronunciation and emotion/performance direction.

### 22.5 — Dialogue Takes & QA
Generated dialogue becomes GeneratedMedia and enters audio QA.

### 22.6 — Lip-Sync Task Integration
Approved video + approved dialogue → LIP_SYNC.

### 22.7 — Multi-Speaker Lip-Sync
Support Shot-level speaker mapping and multiple speakers.

### 22.8 — Lip-Sync QA
Automated evaluation and repair.

### 22.9 — Ambience & SFX
Scene/Shot audio-effects production.

### 22.10 — Music Cue Model
Create MusicCue with theme, mood, duration, entry and exit.

### 22.11 — Music Provider Integration
Provider-neutral music generation.

### 22.12 — Audio Mix
Deterministic audio mixing using FFmpeg or equivalent.

### 22.13 — Integration & Functional Acceptance
Prove one speaking Shot completes video + dialogue + lip-sync + SFX/ambience → approved Shot media.

---

# 7. Phase 23 — Post-Production & Assembly

### 23.1 — Timeline Domain
Introduce Timeline, TimelineTrack and TimelineItem.

### 23.2 — Approved Media Selection
Timelines reference approved GeneratedMedia, never arbitrary files.

### 23.3 — FFmpeg Provider/Executor
Provider capabilities for TRANSCODE, MUX, TRIM, CONCAT and AUDIO_MIX.

### 23.4 — Shot Post-Processing
Upscale, interpolation, transcode and colour adjustments as ProductionTasks.

### 23.5 — Scene Assembly
Create Scene timelines and optional Scene outputs.

### 23.6 — Episode Assembly
Build Episode timeline from approved media.

### 23.7 — Titles & Credits
Configurable title/credit elements.

### 23.8 — Subtitle / Caption Pipeline
Generate SRT/VTT and optional burn-in.

### 23.9 — Episode Audio Mix
Combine dialogue, ambience, SFX and music.

### 23.10 — Post-Production Workspace
Timeline, Audio, Assembly and Finishing.

### 23.11 — Integration & Functional Acceptance
Prove multiple approved Shots assemble into a complete playable Scene and Episode candidate.

---

# 8. Phase 24 — Episode Completion

This is the point where VSCS becomes responsible for a finished deliverable.

### 24.1 — Episode-Level QA
Evaluate shot completeness, order, black frames, audio sync, loudness, duration, technical format, continuity, subtitles and titles.

### 24.2 — Episode Review
Human final review.

### 24.3 — Episode Approval
Freeze timeline, selected media, audio, QA and production revision.

### 24.4 — MasterProfile
Profiles such as Production Master, Streaming Master, Review Copy and Archive Master.

### 24.5 — Master Generation
Deterministic master creation.

### 24.6 — DeliveryArtifact
Controlled delivery objects.

### 24.7 — Export Profiles
Configurable destinations and formats.

### 24.8 — Checksums & Delivery Manifest
Provide reproducible delivery.

### 24.9 — Archive
Project/master archival support.

### 24.10 — Delivery Workspace
Masters, Exports and Archive.

### 24.11 — Integration & Functional Acceptance
One Story-derived Episode must travel entirely through VSCS to an approved, mastered and exported deliverable. This is the first true product-completion milestone.

---

# 9. Phase 25 — Workflow Consolidation & Legacy Retirement

Large cleanup and operator simplification occurs only after the production engine works.

### 25.1 — ProductionWorkflowCoordinator
Simplified orchestration: Analyse & Build Production Plan → Build Production → Generate Schedule → Start Production.

### 25.2 — Unified Issues & Decisions
Consolidate proposal issues, canonical decisions, planning blockers, schedule conflicts, provider failures, QA findings and repair decisions.

### 25.3 — Continuous Production Readiness
Replace manual acceptance commands in normal UI with continuous readiness; retain detailed reports in Advanced mode.

### 25.4 — Dashboard vNext
Overall progress, running tasks, blocked tasks, issues requiring action and next recommended action.

### 25.5 — WorkspaceRegistry
Replace runtime placeholder replacement and MainWindow monkey-patching with explicit workspace registration.

### 25.6 — Story UX Consolidation
Replace individual Phase 19.5 automation commands in normal mode with orchestrated workflow while retaining Advanced access.

### 25.7 — Canonical Library UI Consolidation
Bring Assets, CAPs, References, Behaviour and Voice under one operator-facing Canonical Library.

### 25.8 — Production Navigation Refactor
Adopt Dashboard, Story, Canonical Library, Production, Quality, Post-Production and Delivery.

### 25.9 — Legacy ShotPlanningService Retirement
Migrate and remove original Shot planning authority.

### 25.10 — SSIE Retirement
Extract remaining useful logic, migrate tests and remove SSIE as an architecture.

### 25.11 — ACPP Authority Retirement
Move ACPP to compatibility/import/export status and remove it from live Production Pipeline stages.

### 25.12 — Asset Resolution Consolidation
Remove duplicate legacy user paths.

### 25.13 — Legacy UI Removal
Remove hidden command buttons, placeholder-replacement code, runtime MainWindow monkey patches and obsolete dialogs.

### 25.14 — Integration & Functional Acceptance
Verify the simplified UX still produces identical governed production results. This is where the engineering interface becomes the production product.

---

# 10. Phase 26 — Production Hardening & Series Readiness

This phase should not introduce major new architecture; it proves and hardens the system.

### 26.1 — Real Episode Production
Run an entire representative Episode, preferably with dozens of Shots.

### 26.2 — Failure Injection
Test provider unavailable, GPU failure, corrupt output, cancelled task, stale authority, missing reference, failed QA and application restart.

### 26.3 — Recovery Certification
Verify production resumes without losing governed state.

### 26.4 — Performance Profiling
Measure database, task compilation, graph operations, queue, UI and large media registries.

### 26.5 — Scheduling Optimisation
Only after real data exists: historical duration estimates, resource optimisation, cost-aware scheduling and batch efficiency.

### 26.6 — Production Cost Tracking
Optional operational layer once real usage data exists.

### 26.7 — Production Memory
Capture provider/workflow performance knowledge from real production.

### 26.8 — Multi-Episode Coordination
Extend scheduling to Season/Series scale.

### 26.9 — Project Archive / Restore Certification
Verify complete production portability.

### 26.10 — Product Acceptance

Final target:

> A user can import a Story, approve the automatically generated production plan, resolve only meaningful exceptions, start production, monitor failures and repairs, review the completed Episode, and export a final master without manually operating the internal VSCS engineering pipeline.

---

# 11. Legacy Retirement Timing

Legacy removal is deliberately late.

- Do not remove SSIE, ACPP, old Shot Planning or legacy asset resolution before replacement behaviour is proven unless a specific component directly blocks the new architecture.
- Begin migration during Phases 20–24 only where the replacement fully covers required behaviour.
- Perform systematic retirement in Phase 25 after the production path is complete and regression testing can prove equivalence.

---

# 12. Branching Strategy

Continue branch-per-subphase development.

Each subphase must:

1. implement;
2. test;
3. run mypy where applicable;
4. run Ruff;
5. run relevant regression;
6. perform functional validation;
7. commit;
8. push;
9. receive explicit acceptance before the next gated phase begins unless parallel work is explicitly authorised.

---

# 13. Standard Acceptance Pattern

Every major phase closes with four acceptance levels:

1. **Static acceptance** — Ruff and mypy where applicable.
2. **Unit acceptance** — domain/service behaviour.
3. **Integration acceptance** — cross-service pipeline.
4. **Functional acceptance** — actual operator workflow using a representative VSCS project.

Where live providers are involved, functional acceptance must include actual provider execution rather than mocks.

---

# 14. Milestone Map

| Milestone | Outcome |
|---|---|
| **M1 — Production Intelligence** | Completed with Phase 19.5 |
| **M2 — Production Orchestration** | Phase 19.6 |
| **M3 — Live Production** | Phase 20 |
| **M4 — Self-Correcting Production** | Phase 21 |
| **M5 — Complete Shot Production** | Phase 22 |
| **M6 — Complete Episode Assembly** | Phase 23 |
| **M7 — Deliverable Episode** | Phase 24 |
| **M8 — Production-Grade UX** | Phase 25 |
| **M9 — Series Production Ready** | Phase 26 |

---

# 15. Definition of Usable VSCS

### Usable Production Engine — after Phase 20
VSCS can turn approved Shot authority into actual generated media.

### Usable Episode Production System — after Phase 24
VSCS can produce an entire deliverable Episode.

### Production-Grade Product — after Phase 25/26
VSCS can do so through the simplified workflow, robustly and repeatedly.

---

# 16. Formal Roadmap Statement

Phase 19.6 establishes ProductionTask, ProductionGraph, ProductionScheduler, ProductionResource and ProductionQueue architecture, reusing and modernising the existing Production Pipeline and Render Queue foundations.

Phase 20 connects that orchestration architecture to live production providers and introduces authoritative GeneratedMedia management.

Phase 21 closes the production loop through generated-media QA, structured quality findings, diagnosis, repair and selective regeneration.

Phase 22 makes dialogue, canonical voice identity, TTS, lip-sync, ambience, sound effects, music and audio mixing first-class ProductionTasks.

Phase 23 implements timeline-based post-production, Scene/Episode assembly and finishing.

Phase 24 implements final Episode QA, human release approval, mastering, export and archive, completing the first true end-to-end VSCS product pipeline.

Phase 25 rationalises the operator experience and retires superseded SSIE, ACPP-authority, original Shot-planning and transitional presentation paths only after their replacement architecture has been proven.

Phase 26 hardens the platform through full Episode/Series production, failure and recovery testing, performance optimisation, production memory and multi-Episode coordination.

---

## 17. Roadmap Governance

This file is the authoritative forward roadmap until explicitly superseded by another approved architecture review.

Detailed phase implementation documents may refine subphase numbering, add evidence-driven corrective work, or split acceptance work into smaller increments. They must not silently change the major dependency order or product milestones defined here.

When a detailed implementation phase conflicts with an older roadmap document, this Architecture vNext roadmap governs forward planning unless an explicit later architectural decision states otherwise.
