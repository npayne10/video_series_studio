# Phase 17.6.2 — Functional Gap Analysis

**Document ID:** VSCS-ENG-17.6.2  
**Version:** 1.0  
**Status:** Architecture and Repository Assessment  
**Parent Phase:** 17.6 — Production Workflow and Functional Consolidation  
**Assessment baseline:** Repository state after completion of Phase 17.5.6  

## 1. Purpose

This document compares the approved target architecture of Video Series Studio (VSCS) with the current implementation in the `video_series_studio` repository.

The assessment is based on the approved specifications for:

- Phase 17.6.1.1 — Ideal Production Workflow Specification;
- Phase 17.6.1.2 — Production Object Model;
- Phase 17.6.1.3 — Continuity, Quality and Automation Control Map;
- Phase 17.6.1.3A — Physical Reality Framework;
- Phase 17.6.1.4 — Required VSCS Capability Map;
- the implemented work completed through Phase 17.5.6.

The purpose is not to judge the current application against an earlier prototype goal. It is to determine the shortest, safest path from the current engineering foundation to a coherent production platform capable of producing a trailer, short film, episode, series, or feature film.

## 2. Assessment Principle

The comparison is performed in this order:

```text
Ideal Production Workflow
        ↓
Required VSCS Capability Map
        ↓
Current Repository and UI
        ↓
Functional Gaps
        ↓
Consolidation Roadmap
```

The target system, rather than the current UI, is treated as authoritative.

## 3. Status Classification

Every capability is classified using one of the following states.

| Status | Meaning |
|---|---|
| Complete | Implemented, integrated, tested, and usable for its intended current scope. |
| Mostly Complete | Strong implementation exists, with limited integration or usability work remaining. |
| Partial | Meaningful implementation exists, but important workflow, lifecycle, or UI functions are missing. |
| Foundation | Contracts and services exist, but the user-facing or operational capability is not complete. |
| Stub | A visible placeholder or minimal shell exists without sufficient production behaviour. |
| Missing | No meaningful implementation currently exists. |
| Replace | Existing behaviour conflicts with the target workflow and should be retired or redesigned. |

## 4. Executive Summary

VSCS has a strong technical foundation in the middle of the production pipeline. The following areas are substantially developed:

- project bootstrap and service registration;
- structured story browsing and scene management;
- shot planning;
- Asset Manager data and browsing;
- CAP and canonical-reference services;
- ACPP editing and validation;
- renderer-neutral rendering contracts;
- workflow manifests and compatibility validation;
- ComfyUI adapter foundations;
- Prompt Graph construction, validation, compilation, snapshots, and differencing;
- renderer prompt profiles and preview compilation;
- batch prompt compilation;
- incremental compilation;
- progress, reporting, cancellation, recovery, and restart handling;
- prompt optimisation;
- asset, CAP, and canonical-reference resolution;
- Prompt Graph asset enrichment;
- dependency tracking and selective invalidation.

The application is therefore not an early prototype. It already contains a substantial planning and compilation engine.

However, the complete production path is not yet available. The largest gaps are before and after the current foundation:

```text
Idea and concept development          Missing
Story canon and world management      Mostly missing
Script/manuscript production import   Partial
Production hierarchy                  Partial
Asset lifecycle editing               Incomplete
Continuity state management           Foundation only
Physical Reality Framework            Specification only
Prompt and batch operation UI         Partial or missing
ComfyUI execution                     Missing
Render queue and output review        Missing
Voice and dialogue production         Missing
Lip-sync execution                    Missing
Audio and music production            Missing
Shot QC and approval                   Missing
Timeline and scene assembly            Missing
Post-production and export             Missing
Distribution and archive               Missing
```

The most important conclusion is:

> VSCS currently has a mature planning, canonical-asset, prompt-compilation, and dependency foundation, but it does not yet provide a complete producer-guided path from project creation to finished media.

The next development effort should not immediately add isolated modules. It should first consolidate the workflow, complete object lifecycles, standardise help and navigation, and create the Production Workspace that will coordinate the remaining operational modules.

## 5. Current Architectural Strengths

### 5.1 Service-oriented application architecture

The repository uses explicit application services and dependency registration rather than embedding production logic directly in widgets. This is a strong basis for consolidation because existing capabilities can be reorganised in the UI without discarding core logic.

### 5.2 Tested production contracts

Rendering, continuity, voice, lip-sync, workflow, Prompt Graph, batch compilation, recovery, and asset resolution have typed contracts and focused tests. These contracts reduce the risk of later renderer and media integration.

### 5.3 Renderer-neutral design

The Prompt Graph and rendering contracts do not make ComfyUI the owner of the production model. This preserves future renderer flexibility.

### 5.4 Canonical asset foundation

Asset, CAP, approved-reference resolution, dependency fingerprints, Prompt Graph enrichment, and selective invalidation are already connected. This is one of the most difficult continuity foundations and should be preserved.

### 5.5 Incremental and recoverable automation

Batch prompt compilation already supports deterministic order, failure isolation, cancellation, reporting, history, incremental rebuilds, recovery checkpoints, and restart continuation. These patterns should be reused for rendering, audio, lip-sync, QC, and export jobs.

## 6. Workflow Coverage Matrix

| Ideal workflow stage | Current status | Current evidence | Required work |
|---|---|---|---|
| Idea capture | Missing | No dedicated concept object or workspace | Add Idea Capture Workspace and persistent concept model. |
| Concept development | Missing | No logline, audience, tone, format, or concept approval workflow | Add Concept Editor and approval lifecycle. |
| Story world and canon | Partial | Story structure exists; CAPs provide asset canon | Add project-level Canon Manager, world bible, timeline, rules, factions, technology, and conflict validation. |
| Character development | Partial | Characters can exist as assets and CAPs | Add character bible, relationships, arcs, knowledge state, voice linkage, and lifecycle UI. |
| Narrative architecture | Partial | Story Browser, episodes/scenes, and scene services exist | Add series, season, act, sequence, trailer-beat, and complete production hierarchy. |
| Production structure definition | Partial | Episode, scene, and shot IDs exist | Add generic Production, Series, Season, Film, Trailer, Sequence, and Clip management. |
| Script development | Partial | Story data can be entered and browsed | Add screenplay/manuscript editor, import, revision, and approval workflow. |
| Script and story breakdown | Partial | Story integration and structured scenes exist | Add import parsing, entity extraction, asset proposals, dialogue register, and breakdown approval. |
| Production planning | Missing | No full production schedule or readiness workspace | Add production planner, milestones, dependencies, cost/runtime estimates, and blocked-work view. |
| Asset inventory and discovery | Mostly Complete | Asset service, browser, filters, ACPP selection, resolution services | Complete edit, duplicate, archive, usage, variant, and dependency-inspection workflows. |
| Canonical asset development | Mostly Complete | CAP and canonical-reference services, approvals, readiness, primary reference selection | Improve editing, versioning, supersession, previews, help, and multi-viewpoint workflows. |
| Shot planning | Mostly Complete | Shot Planner, camera/lighting selection, continuity and blocking contracts | Add approval lifecycle, variants, physical constraints, clip subdivision, and improved workflow guidance. |
| Storyboard and previsualisation | Missing | Storyboard reference field exists | Add storyboard manager, storyboard generation/import, animatic builder, and preview review. |
| ACPP creation | Mostly Complete | ACPP Editor, validation, asset browsing, resolution | Add full inheritance, physical constraints, version approval, and workflow guidance. |
| Prompt Graph construction | Complete for current scope | Builder, validation, compiler, snapshots, differencing, enrichment | Add canon, continuity-state, dialogue, and Physical Reality enrichment. |
| Prompt compilation | Complete for current scope | Profiles, preview, optimisation, batch, incremental, reporting, recovery | Add coherent production UI, approval gates, and direct hand-off to render jobs. |
| Preview generation | Missing operational execution | Preview prompt profiles exist | Add workflow submission, renderer execution, output registration, and preview review. |
| Production rendering | Missing | Contracts, manifests, validator, adapter foundation exist | Implement ComfyUI execution service, queue, progress, retries, recovery, outputs, and UI. |
| Voice and dialogue production | Foundation | Voice contracts exist | Implement voice profiles, provider adapters, generation jobs, pronunciation, audio outputs, and review. |
| Lip-sync | Foundation | Lip-sync contracts exist | Implement execution adapters, face/speaker mapping, output registration, and QC. |
| Sound and music | Missing | Audio contracts are limited | Add sound profiles, generation/import, stems, music cues, ambience, mixing, and review. |
| Shot QC | Missing | Validation exists for data, not rendered media approval | Add technical QC, creative review, continuity review, physical plausibility review, and approvals. |
| Scene assembly | Missing | No timeline production workflow | Add scene timelines, tracks, media placement, edit points, audio alignment, and scene approval. |
| Episode/film/trailer assembly | Missing | Story hierarchy exists, but no media assembly | Add production timeline, trailer source mapping, title cards, runtime validation, and cut versions. |
| Post-production | Missing | No integrated finishing workspace | Add colour, audio finishing, subtitles, captions, graphics, and mastering hand-off. |
| Final QA | Missing | No complete master QA | Add conformance validation, narrative completion, continuity, captions, and release approval. |
| Export and delivery | Missing | No deliverable manager | Add export profiles, deliverables, metadata, checksums, and platform presets. |
| Distribution | Missing | No distribution records | Add optional publication and delivery tracking. |
| Archive and reuse | Partial | Project files and canonical assets persist | Add archive manifests, integrity checks, restore tests, and reusable production packages. |

## 7. Capability Domain Assessment

### 7.1 Workspace and Project Management — Partial

#### Present

- Application bootstrap and shutdown lifecycle.
- Project creation and opening.
- Project-based storage and database context.
- Configuration and environment services.
- Main window and workspace integration.

#### Gaps

- Project editing after creation is incomplete or not consistently exposed.
- No project template workflow for series, film, trailer, or short film.
- No project archive, restore, migration, duplication, or health summary.
- No clear current-production identity separate from the project.
- No recommended-next-action guidance.

#### Required resolution

Create a Project Dashboard with project metadata, production list, defaults, health, recent activity, blockers, and next actions.

### 7.2 Idea and Concept Development — Missing

No dedicated objects or windows currently support idea capture, concept briefs, loglines, target audience, genre, tone, format, runtime targets, or concept approval.

#### Required resolution

Add:

- Idea Record;
- Concept Brief;
- Idea Capture Workspace;
- Concept Editor;
- concept versioning and approval;
- conversion from approved concept to Production.

### 7.3 Story, Canon, and Adaptation — Partial

#### Present

- Story Browser and Story Browser v2.
- Episode and scene structures.
- Scene creation and editing workflow.
- Story integration with shot planning and ACPP.
- Source story/manuscript concepts in earlier project work.

#### Gaps

- No authoritative project-wide Canon Manager.
- No world bible, series bible, season bible, or character relationship manager.
- No story timeline and chronology conflict service.
- No adaptation mapping from manuscript sections to episodes, scenes, and shots.
- No clear source-text provenance through the complete production chain.

#### Required resolution

Introduce a Story and Canon Workspace above the current Story Browser. Retain the current browser as the structural navigation component rather than making it responsible for all canon functions.

### 7.4 Production Structure Management — Partial

#### Present

- Episode, scene, and shot structures.
- Deterministic IDs and ordering.
- Reordering within current scopes.

#### Gaps

- No generic Production aggregate.
- Series, Season, Film, Short Film, Trailer, Teaser, Act, Sequence, Trailer Beat, and Clip are not all represented as first-class editable objects.
- Story order and production order are not fully separated throughout the UI.
- Trailer reuse of existing source shots is not represented.

#### Required resolution

Implement one generic production hierarchy capable of representing all production types without duplicating separate architectures.

### 7.5 Script and Narrative Breakdown — Partial

#### Present

- Structured scene data.
- Story browsing and scene editing.
- Dialogue and action can be represented in current production objects.

#### Gaps

- No complete screenplay editor.
- No manuscript/script importer with reviewable parsing.
- No entity extraction or asset requirement proposals.
- No formal dialogue register.
- No approved breakdown state.

#### Required resolution

Implement import and breakdown as assisted workflows. Automated extraction must produce reviewable proposals rather than silently modifying production data.

### 7.6 Production Planning — Missing

No unified production schedule, dependency plan, milestone view, render estimate, cost estimate, or production-readiness dashboard exists.

#### Required resolution

The Production Workspace should become the owner of planning, priorities, readiness, blockers, queues, approvals, and progress.

### 7.7 Asset Management — Mostly Complete, lifecycle incomplete

#### Present

- Asset service and persistence.
- Asset creation.
- Asset browsing, filtering, category selection, and resolution-aware readiness.
- ACPP asset selection without manual ID entry.
- CAP and reference linkage.
- Dependency fingerprinting and affected-shot lookup.

#### Gaps

- Editing assets after creation is not consistently available in the UI.
- Duplicate, archive, controlled delete, variant management, usage inspection, dependency inspection, and version history are incomplete.
- Help and guided workflow are inconsistent.
- Asset ownership and category-specific editors are limited.

#### Required resolution

Complete the Asset Manager as the single maintenance location for asset create, inspect, edit, duplicate, archive, delete, variants, usages, dependencies, and history.

### 7.8 CAP and Canonical Reference Management — Mostly Complete, usability incomplete

#### Present

- CAP create, get, list, update, and delete services.
- Approved status and version fields.
- Canonical-reference lifecycle, candidate, approval, locking, unlocking, archive, and primary selection.
- Canonical resolution and production-readiness diagnostics.
- Reference dependency checksums.

#### Gaps

- CAP editing and version/supersession workflows need clearer UI ownership.
- Reference preview and viewpoint management are limited.
- Help, field guidance, readiness checklist, and next-step guidance are inconsistent.
- Approved CAP lifecycle should explicitly support superseding rather than destructive changes.

#### Required resolution

Consolidate CAP and references into a Canonical Asset Workspace with asset context, CAP versions, references, approval, readiness, help, and usage impact.

### 7.9 Physical Reality and Plausibility — Missing

The Physical Reality Framework is defined in architecture documentation but not implemented in the application.

#### Missing objects

- PhysicalEnvironmentProfile;
- PlanetProfile;
- AtmosphereProfile;
- TechnologyProfile;
- VehiclePhysicsProfile;
- HumanCapabilityProfile;
- MaterialProfile;
- WeaponProfile;
- EnergyProfile;
- PhysicsConstraint;
- PhysicsOverride;
- PhysicsValidationResult.

#### Missing services

- VSCS Physics Engine;
- Physics Validation Service;
- Environment and Technology services;
- Prompt Physics Injector;
- Physics QC Service.

#### Required resolution

Begin with profile-driven rules and deterministic validation. Do not attempt full simulation in the first implementation.

### 7.10 Continuity Management — Foundation

#### Present

- Rendering continuity contracts.
- Shot continuity references and notes.
- Start/end media contracts.
- Asset/CAP/reference continuity through canonical resolution.
- Dependency invalidation.

#### Gaps

- No central continuity state store.
- No structured state transitions for characters, props, locations, damage, costume, emotion, position, lighting, or audio environment.
- No Continuity View.
- No cross-scene or cross-episode continuity graph.
- No override approval workflow.

#### Required resolution

Create Continuity State and Transition objects, then integrate them with scenes, shots, ACPP, Prompt Graph, previews, and QC.

### 7.11 Shot Planning and Previsualisation — Mostly Complete / Missing previsualisation

#### Present

- Shot planning service and dialog.
- Shot purpose, size, movement, lens, duration, camera and lighting profiles.
- Blocking and continuity notes.
- Asset counts and story-browser integration.
- Shot ordering and validation.

#### Gaps

- No complete approval lifecycle.
- No physical constraints.
- No shot variants.
- Clip subdivision is not a first-class workflow.
- Storyboard reference exists, but storyboard and animatic production do not.
- Help and next-step guidance require standardisation.

### 7.12 ACPP Production Packaging — Mostly Complete

#### Present

- ACPP Editor and service.
- Asset bindings and browser selection.
- Narrative, prompt, output, continuity, blocking, and profile information.
- Validation and persistence.
- Story-browser integration.

#### Gaps

- No Physical Reality section.
- Continuity is not yet based on structured state transitions.
- Dialogue/voice/audio linkage is incomplete.
- Version approval and supersession are not fully exposed.
- No production-readiness workflow leading directly to Prompt Preview and rendering.

### 7.13 Prompt Graph and Compilation — Complete foundation, UI consolidation required

#### Present

- Core graph model.
- Builder and resolver.
- Validation and diagnostics.
- Compiler.
- Snapshots and differencing.
- Renderer profiles and prompt preview contracts.
- Batch compilation, scheduling, cancellation, reporting, history, recovery, and restart.
- Incremental compilation and invalidation.
- Prompt optimisation with mandatory-detail protection.
- Asset, CAP, and reference enrichment.

#### Gaps

- No full production-facing Prompt Preview and Batch Compilation workspace.
- Canon, continuity-state, physical-reality, voice, and audio enrichment remain incomplete.
- Compiled packages do not yet flow directly into executable render jobs.
- Approval state between preview compilation and rendering requires definition.

### 7.14 Renderer and Workflow Management — Foundation

#### Present

- Rendering contracts.
- Quality levels.
- Continuity, voice, lip-sync, and media contracts.
- Workflow manifests, discovery, validation, diagnostics, and reference manifests.
- ComfyUI adapter foundation.

#### Gaps

- No operational ComfyUI server connection and execution lifecycle.
- No workflow mapping editor.
- No UI for workflow diagnostics, node/resource mapping, or compatibility remediation.
- No model inventory and health view.
- No workflow version-management UI.

### 7.15 Render Queue and Media Generation — Missing operational capability

The system can prepare contracts and prompts but cannot yet produce a video through the application.

#### Required modules

- Production Render Workspace;
- ComfyUI Connection Manager;
- ComfyUI Execution Service;
- Render Queue Manager;
- Render Scheduler;
- Render Progress Monitor;
- Render Recovery Service;
- Render Output Registry;
- Output Viewer and Comparison Workspace.

This is the principal production-blocking gap after consolidation.

### 7.16 Voice, Dialogue, Audio, and Lip-sync — Foundation / Missing execution

#### Present

- Voice and lip-sync contracts.
- Dialogue information in shots and ACPP.

#### Gaps

- No voice-profile management UI.
- No TTS/provider adapters or generation jobs.
- No pronunciation dictionary.
- No audio output registry or waveform/timing review.
- No lip-sync executor.
- No speaker/face mapping UI.
- No ambience, Foley, effects, or music workflow.

### 7.17 Quality Control and Review — Missing

Current validators check structured data and technical compatibility. They do not provide the complete human review and approval model required for generated media.

#### Required capabilities

- review records;
- approval records tied to versions;
- revision requests;
- preview comparison;
- shot QC;
- continuity QC;
- Physical Reality QC;
- audio and lip-sync QC;
- technical file inspection;
- final QA.

### 7.18 Timeline, Assembly, and Post-production — Missing

No integrated timeline or media assembly system currently completes scenes, episodes, films, or trailers.

#### Required resolution

The first implementation should focus on a practical assembly layer rather than attempting to replace a full professional NLE immediately. VSCS should create and manage timelines, source media, audio stems, transitions, titles, markers, and export hand-off. External-editor interchange may be supported where appropriate.

### 7.19 Delivery, Distribution, and Archive — Missing / Partial

Project storage exists, but final deliverables, distribution records, archive manifests, restore verification, and reusable completed-production packages are not present.

### 7.20 Platform Services and Governance — Partial

#### Present

- dependency injection;
- configuration;
- logging;
- database management;
- plugins;
- deterministic IDs in key modules;
- checksums and provenance in prompt/render foundations.

#### Gaps

- central audit event service;
- notification centre;
- project-wide approval service;
- common version/supersession framework;
- job orchestration shared by all media types;
- storage quota and cleanup service;
- unified search;
- contextual help framework;
- migration and archive governance.

## 8. UI Assessment

### 8.1 General finding

The current UI is organised primarily around individual tools and dialogs. The target workflow requires a production-oriented shell that tells the user:

- where they are in the production lifecycle;
- what is ready;
- what is blocked;
- what the next action is;
- which approvals are required;
- which jobs are running;
- what changed and what became invalid.

### 8.2 Required common window standard

Every major editor should consistently include:

- object identity and current status;
- Save, Cancel, and destructive-action conventions;
- contextual Help;
- concise field guidance;
- readiness and validation summary;
- dependency and impact information where relevant;
- clear next-step action;
- keyboard focus and predictable tab order;
- browse controls instead of raw-ID entry;
- edit capability after creation;
- version and approval information.

### 8.3 Window-specific findings

| Window or area | Current assessment | Required action |
|---|---|---|
| New Scene | Strong guidance pattern | Use as one reference for help and workflow guidance. |
| Story Browser | Strong structural navigation | Extend above scene level to production hierarchy and canon. |
| Shot Planner | Functional and tested | Add help, approval, variants, physics, clips, and next-step navigation. |
| Asset Manager | Useful but lifecycle incomplete | Add edit, duplicate, archive, variants, usage, dependencies, history, help. |
| Asset Picker | Strong production-ready selection | Retain and standardise for all asset-consuming workflows. |
| CAP Manager | Strong service foundation | Add unified canonical workspace, help, versions, readiness, usage impact. |
| Canonical References | Lifecycle exists | Improve previews, viewpoints, multi-reference workflow, help. |
| ACPP Editor | Substantial editor | Add readiness journey, structured continuity, physics, audio, versions, direct prompt navigation. |
| Prompt Preview | Technical foundation exists | Create a full workspace for comparison, diagnostics, approval, and batch submission. |
| Workflow Diagnostics | Backend capability exists | Add visible remediation and resource-health UI. |
| Batch Compilation | Strong backend | Add queue, progress, history, reports, recovery, and approval UI. |
| Render Queue | Missing | New workspace required. |
| Media Review | Missing | New preview/production comparison and approval workspace required. |
| Timeline | Missing | New assembly workspace required. |
| Help System | Inconsistent | Create shared contextual-help framework and standards. |

## 9. Full Object Lifecycle Assessment

| Object | Create | View | Edit | Duplicate | Archive | Delete | Approve/version | Assessment |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Project | Yes | Yes | Partial | No | No | Limited | No | Partial |
| Production | No | No | No | No | No | No | No | Missing |
| Episode | Yes | Yes | Partial | Limited | Limited | Limited | Limited | Partial |
| Scene | Yes | Yes | Yes | Limited | Limited | Yes | Limited | Mostly complete |
| Shot | Yes | Yes | Yes | Limited | No | Yes | Limited | Mostly complete |
| Clip | No | No | No | No | No | No | No | Missing |
| Asset | Yes | Yes | UI gap | No | Limited | Limited | Partial | Incomplete lifecycle |
| CAP | Yes | Yes | Service exists | No | Limited | Yes | Partial | Mostly complete backend |
| Canonical Reference | Yes | Yes | Controlled | No | Yes | Yes when unlocked | Yes | Strong backend |
| ACPP | Yes | Yes | Yes | Limited | No | Yes | Limited | Mostly complete |
| Prompt Graph | Automatic | Technical | Rebuilt | Snapshot | Historical | No direct delete | Checksummed | Strong foundation |
| Render Job | Contracts only | No | No | No | No | No | No | Missing execution |
| Render Output | No | No | No | No | No | No | No | Missing |
| Review | No | No | No | No | No | No | No | Missing |
| Timeline | No | No | No | No | No | No | No | Missing |
| Deliverable | No | No | No | No | No | No | No | Missing |

## 10. End-to-End Production Path Assessment

### 10.1 Trailer

#### Current achievable path

```text
Create Project
→ Create story structure manually
→ Create scenes
→ Create shots
→ Create assets
→ Create CAPs
→ Approve references
→ Bind assets in ACPP
→ Build and compile Prompt Graphs
```

#### Current stopping point

The application cannot yet execute ComfyUI workflows, register generated shots, perform review, generate voice/lip-sync, assemble a trailer timeline, or export a final trailer.

#### Assessment

Planning and prompt preparation are advanced. Media production and assembly are missing.

### 10.2 Short film

The same stopping point applies. Additional missing requirements include multi-scene assembly, sound design, scene QC, and final mastering.

### 10.3 Episode

The story and shot planning foundations support episodic work, but season/episode governance, continuity across episodes, render execution, audio, QC, and timeline assembly are missing.

### 10.4 Feature film

The current architecture can eventually scale to a film, but production scheduling, large-scale job orchestration, storage management, review, timeline assembly, and delivery must be completed first.

### 10.5 Series

The greatest additional gaps are series/season structures, canon governance, cross-episode continuity, asset variants across story time, and production-wide progress management.

## 11. Continuity Gap Assessment

### Strong current controls

- stable asset IDs;
- CAP descriptions and approved references;
- canonical-resolution readiness;
- reference roles and locking;
- Prompt Graph asset enrichment;
- dependency fingerprints;
- affected-shot tracking;
- selective prompt invalidation;
- rendering continuity contracts.

### Missing controls

- structured continuity states;
- state inheritance rules in the live application;
- character costume, injury, emotion, position, and knowledge state;
- prop ownership and condition;
- location, weather, damage, and time state;
- camera axis and eyeline continuity;
- lighting direction continuity;
- audio-environment continuity;
- continuity review and override approval;
- visual comparison against prior approved outputs.

### Priority

Continuity State Management is Priority 1 because render generation without it would undermine the central project requirement.

## 12. Physical Reality Gap Assessment

The framework is approved but has no implementation.

### Minimum first implementation

1. Project Scientific Rules.
2. Environment and Planet Profiles.
3. Technology Profiles.
4. Human Capability Profiles.
5. Vehicle Physics Profiles.
6. Rule-based constraints and severity.
7. Shot and ACPP physical requirements.
8. Prompt Graph physical-reality nodes.
9. Prompt compiler protection of physical constraints.
10. Preview and render QC checklist integration.

### Deferred advanced implementation

- numerical orbital mechanics;
- structural simulation;
- fluid simulation;
- detailed thermal modelling;
- automated computer-vision plausibility scoring.

## 13. Quality Gap Assessment

### Present

- validation diagnostics;
- readiness checks for assets and canonical references;
- Prompt Graph validation;
- workflow compatibility;
- preview and production quality profiles in contracts;
- batch reporting and history.

### Missing

- review records;
- version-specific approvals;
- revision requests;
- media QC;
- preview approval;
- production render approval;
- audio/lip-sync approval;
- scene approval;
- final-master approval;
- release conformance.

## 14. Automation Gap Assessment

### Strong current automation foundation

- deterministic source ordering;
- Prompt Graph construction;
- prompt compilation;
- renderer profiles;
- optimisation;
- batch scheduling;
- incremental recompilation;
- cancellation;
- reporting;
- recovery;
- dependency invalidation.

### Missing operational automation

- script ingestion and extraction;
- ACPP inheritance from structured continuity and physics;
- render submission and execution;
- render retry and output registration;
- voice generation;
- lip-sync execution;
- technical media QC;
- initial timeline assembly;
- export jobs;
- notifications and approval routing.

### Design requirement

All new job types should reuse one generic job, progress, retry, recovery, and history architecture rather than creating isolated schedulers.

## 15. Technical Debt and Consolidation Register

### 15.1 Obsolete or changing workflows

Earlier workflows remain in the repository even where later phases introduced improved replacements. A repository-wide reachability and ownership review is required before deletion.

### 15.2 Creation without maintenance

Some objects can be created but are difficult or impossible to edit through the UI. Asset editing is the clearest example.

### 15.3 Raw-ID interactions

Phase 17.5 improved ACPP asset selection, but all remaining raw-ID fields should be identified and replaced with browse, search, or contextual selection.

### 15.4 Inconsistent help

The New Scene guidance pattern is not consistently applied to CAP, Asset, Shot, ACPP, and other complex editors.

### 15.5 Distributed workflow ownership

Some operations are technically available but not discoverable because ownership is spread across dialogs and story integration code.

### 15.6 Bootstrap timing and optional registration

Asset resolution registration currently depends on project and service availability. Consolidation should define clear project-open and project-close lifecycle hooks for project-bound services.

### 15.7 In-memory production state

Some indexes and histories are currently in memory. Production-critical continuity, dependency, job, review, and approval data will require durable persistence.

### 15.8 Documentation and implementation drift

Architecture documents must include repository impact and implementation status so approved target behaviour is not mistaken for completed functionality.

## 16. Priority Matrix

### Priority 1 — Production blocking

- Production hierarchy and Production Workspace.
- Full Asset and CAP editing lifecycle.
- Structured continuity states and inheritance.
- Physical Reality profile foundation.
- Prompt Preview and approval workspace.
- ComfyUI execution.
- Render queue, outputs, review, and recovery.
- Voice generation and lip-sync execution.
- Shot QC and approvals.
- Basic timeline and trailer/scene assembly.
- Deliverable export.

### Priority 2 — Strong productivity and quality improvement

- Idea and concept workspace.
- Canon and world management.
- Script import and breakdown.
- Production planning and readiness dashboard.
- Storyboards and animatics.
- Audio, ambience, Foley, and music management.
- Version/supersession framework.
- Audit and notification services.

### Priority 3 — Advanced production quality

- Automated visual continuity comparison.
- Advanced Physical Reality validation.
- Cost estimation and distributed scheduling.
- Advanced post-production integration.
- Platform-specific delivery management.

### Priority 4 — Future expansion

- Full numerical physics simulation.
- Automated editing intelligence.
- Direct multi-platform publication.
- Enterprise collaboration and permissions.

## 17. Recommended Consolidation Roadmap

The earlier provisional Phase 17.6 structure should now be refined as follows.

### Phase 17.6.3 — Workflow UX Consolidation

- Define the definitive user journey.
- Create production navigation and next-action logic.
- Standardise window behaviour.
- Identify obsolete and duplicate paths.
- Add shared contextual help framework.

### Phase 17.6.4 — Object Lifecycle Completion

- Complete edit, duplicate, archive, delete, version, and approval functions.
- Begin with Project, Asset, CAP, Reference, Scene, Shot, and ACPP.
- Add usage and dependency impact views.

### Phase 17.6.5 — Production Structure and Workspace Foundation

- Add Production, Series, Season, Film, Trailer, Sequence, and Clip objects.
- Implement Production Workspace and readiness dashboard.
- Connect current Story Browser, Shot Planner, Asset Manager, CAP, and ACPP tools.

### Phase 17.6.6 — Continuity and Physical Reality Foundation

- Implement structured continuity states and transitions.
- Implement rule-based Physical Reality profiles.
- Enrich ACPP and Prompt Graph.

### Phase 17.6.7 — Prompt-to-Render Operational Bridge

- Production Prompt Preview UI.
- Workflow selection and remediation.
- ComfyUI connection and execution.
- Render queue, progress, recovery, outputs, and review.

### Phase 17.6.8 — Voice, Lip-sync, QC, and Assembly Foundation

- Voice profiles and generation.
- Lip-sync execution.
- Shot QC and approval.
- Basic timeline and scene/trailer assembly.

### Phase 17.6.9 — Consolidation Certification

- End-to-end trailer test.
- Workflow usability review.
- Regression and repository cleanup.
- Final roadmap for full episode production.

## 18. Minimum Usable Trailer Path

The shortest useful target is:

```text
Create Project
→ Create Trailer Production
→ Define Trailer Beats
→ Create or link Scenes
→ Plan Shots and Clips
→ Resolve Assets, CAPs, and References
→ Validate Continuity and Physical Reality
→ Build ACPP
→ Preview Prompt
→ Generate Preview
→ Review and Approve
→ Generate Production Shot
→ Generate Voice and Lip-sync where required
→ Perform Shot QC
→ Assemble Trailer Timeline
→ Export Trailer
```

Completing this path provides a real production result while exercising architecture that later scales to episodes and films.

## 19. Repository Impact

### Existing modules to retain and extend

```text
src/vscs/application/projects
src/vscs/application/story
src/vscs/application/shots
src/vscs/application/assets
src/vscs/application/caps
src/vscs/application/acpp
src/vscs/application/asset_resolution
src/vscs/application/prompt_graph
src/vscs/application/rendering
src/vscs/presentation/story_integration.py
src/vscs/presentation/dialogs
src/vscs/presentation/widgets
src/vscs/presentation/windows
```

### New application domains anticipated

```text
src/vscs/application/productions
src/vscs/application/concepts
src/vscs/application/canon
src/vscs/application/continuity
src/vscs/application/physics
src/vscs/application/jobs
src/vscs/application/media
src/vscs/application/voice
src/vscs/application/audio
src/vscs/application/reviews
src/vscs/application/timelines
src/vscs/application/deliverables
src/vscs/application/audit
src/vscs/application/notifications
```

### New primary UI areas anticipated

```text
Production Workspace
Project Dashboard
Concept Workspace
Canon and World Workspace
Continuity View
Physical Reality Profiles
Prompt Preview Workspace
Render Queue and Output Review
Voice and Lip-sync Workspace
QC and Review Centre
Timeline and Assembly Workspace
Deliverables Workspace
```

### Existing UI requiring consolidation

- Project windows and menus.
- Story Browser and story-integration actions.
- Asset Manager and Asset Picker.
- CAP and Canonical Reference windows.
- Shot Planner.
- ACPP Editor.
- Prompt preview and batch functions.
- Workflow diagnostics.

### No code deletion in this phase

This phase is analytical. Existing code should not be deleted until Phase 17.6.3 identifies confirmed duplicate, obsolete, or unreachable paths and regression coverage exists.

## 20. Acceptance Criteria

Phase 17.6.2 is complete when:

1. Every production stage from Phase 17.6.1.1 has been classified.
2. Every capability domain from Phase 17.6.1.4 has been assessed.
3. Current strengths and production-blocking gaps are explicit.
4. Asset, CAP, continuity, Physical Reality, prompt, rendering, audio, QC, timeline, and delivery gaps are covered.
5. UI and object lifecycle deficiencies are recorded.
6. Technical debt and obsolete workflow risks are identified without premature deletion.
7. The minimum trailer production path is defined.
8. The recommended consolidation roadmap is actionable.
9. Repository impact is documented.

## 21. Phase Decision

The current VSCS foundation is suitable for continued development. A rewrite is not recommended.

The correct strategy is:

```text
Preserve the tested application services and contracts
→ Consolidate workflow and UI ownership
→ Complete object lifecycles
→ Add Production, Continuity, and Physical Reality foundations
→ Connect compiled prompts to real rendering
→ Add media review, audio, QC, and assembly
```

The next approved phase should be:

# Phase 17.6.3 — Workflow UX Consolidation

Its first task should define the definitive start-to-finish user journey and convert that journey into the application navigation, workspace layout, contextual help standard, and recommended-next-action model.