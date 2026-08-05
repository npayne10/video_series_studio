# Phase 17.6.1.4 — Required VSCS Capability Map

**Document ID:** VSCS-ENG-17.6.1.4  
**Version:** 1.0  
**Status:** Architecture Specification  
**Parent Phase:** 17.6.1 — Ideal End-to-End Production Workflow  

## 1. Purpose

This specification translates the approved ideal production workflow, production object model, continuity and quality controls, automation rules, and Physical Reality Framework into the complete capability set required by Video Series Studio (VSCS).

The capability map defines what VSCS must support regardless of the current implementation. It is the target architecture against which the existing application will be assessed during Phase 17.6.2.

This document does not assume that every capability must be delivered immediately. It identifies:

- the complete target capability set;
- the minimum viable production path;
- required platform services;
- module ownership boundaries;
- capability dependencies;
- human approval gates;
- future expansion points.

## 2. Governing Production Model

VSCS is governed by five linked systems:

```text
Story Canon
    ↓
Physical Reality
    ↓
Continuity
    ↓
Quality
    ↓
Automation
```

The governing interpretation is:

- **Story Canon** defines what is true.
- **Physical Reality** defines what is possible.
- **Continuity** ensures truth and state remain consistent over time.
- **Quality** verifies that the intended result was achieved.
- **Automation** accelerates production without bypassing the first four controls.

Every major VSCS module must declare how it participates in these systems.

## 3. Target User Journey

The target end-to-end production path is:

```text
Create Project
→ Capture Idea
→ Develop Concept
→ Build Story World and Canon
→ Define Characters
→ Structure Narrative
→ Create or Import Script
→ Break Script into Production Data
→ Plan Production
→ Register Assets
→ Create and Approve CAPs
→ Approve Canonical References
→ Plan Shots
→ Create Storyboards or Previsualisation
→ Build ACPP Packages
→ Construct Prompt Graphs
→ Compile and Optimise Prompts
→ Generate Previews
→ Review and Approve Previews
→ Render Production Shots
→ Generate Dialogue and Audio
→ Apply Lip-sync
→ Perform Shot QC
→ Assemble Scenes
→ Assemble Episode, Film, or Trailer
→ Complete Post-production
→ Perform Final QA
→ Export Deliverables
→ Distribute
→ Archive
```

The VSCS user interface must make this sequence understandable and navigable.

## 4. Capability Domains

The complete target system is divided into twenty capability domains:

1. Workspace and Project Management
2. Idea and Concept Development
3. Story, Canon, and Adaptation
4. Production Structure Management
5. Script and Narrative Breakdown
6. Production Planning
7. Asset Management
8. CAP and Canonical Reference Management
9. Physical Reality and Plausibility
10. Continuity Management
11. Shot Planning and Previsualisation
12. ACPP Production Packaging
13. Prompt Graph and Prompt Compilation
14. Renderer and Workflow Management
15. Render Queue and Media Generation
16. Voice, Dialogue, Audio, and Lip-sync
17. Quality Control and Review
18. Timeline, Assembly, and Post-production
19. Delivery, Distribution, and Archive
20. Platform Services and Governance

## 5. Workspace and Project Management

### 5.1 Required capabilities

VSCS must support:

- creating, opening, closing, editing, duplicating, archiving, and deleting projects;
- project templates for series, film, short film, trailer, teaser, and promotional work;
- project-wide defaults for frame rate, aspect ratio, renderer, quality profile, naming, and storage;
- project metadata and ownership;
- project health and readiness summaries;
- recent-project navigation;
- project backup, restore, and archive;
- project migration between schema versions;
- validation of project folders and required resources.

### 5.2 Required modules

```text
Workspace Manager
Project Manager
Project Template Manager
Project Configuration Manager
Project Migration Service
Project Backup and Restore Service
```

### 5.3 Required UI behavior

The user must be able to identify:

- which project is active;
- which production is active;
- project storage location;
- project readiness and blockers;
- the recommended next action.

## 6. Idea and Concept Development

### 6.1 Required capabilities

VSCS must support:

- idea capture;
- working titles;
- concept briefs;
- loglines;
- genre, tone, audience, format, and runtime targets;
- creative references;
- concept status and approval;
- revision history;
- conversion of an approved concept into a production.

### 6.2 Required modules

```text
Idea Capture Workspace
Concept Editor
Creative Brief Manager
Concept Review and Approval Service
```

### 6.3 Automation

The system may provide advisory assistance for:

- logline drafting;
- format selection;
- runtime estimation;
- concept completeness;
- thematic consistency.

Human approval remains mandatory.

## 7. Story, Canon, and Adaptation

### 7.1 Required capabilities

VSCS must support:

- story source import;
- structured story creation;
- world bibles;
- character bibles;
- series and season bibles;
- canon entries;
- timeline events;
- relationships;
- organisations, factions, technologies, and locations;
- canon versioning and approval;
- canon conflict detection;
- adaptation mapping from novels, manuscripts, and scripts into production objects;
- traceability from source text to episode, sequence, scene, and shot.

### 7.2 Required modules

```text
Story Source Manager
Story Browser
Canon Manager
Timeline Manager
Character Bible Manager
World Bible Manager
Series Bible Manager
Adaptation Mapping Manager
Canon Conflict Service
```

### 7.3 Key requirement

Canon must be structured and queryable. It must not exist only as unstructured notes.

## 8. Production Structure Management

### 8.1 Required capabilities

VSCS must support a shared hierarchy for:

```text
Project
→ Production
→ Series / Film / Short / Trailer
→ Season / Act / Trailer Beat
→ Episode / Sequence
→ Scene
→ Shot
→ Clip
```

The hierarchy must support:

- stable IDs;
- story order;
- production order;
- runtime roll-up;
- reordering;
- duplication;
- archiving;
- status tracking;
- ownership validation;
- parent-child navigation;
- cross-production reuse for trailer source shots.

### 8.2 Required modules

```text
Production Manager
Series Manager
Season Manager
Episode Manager
Film Structure Manager
Trailer Structure Manager
Sequence Manager
Scene Manager
Shot Manager
Clip Manager
```

## 9. Script and Narrative Breakdown

### 9.1 Required capabilities

VSCS must support:

- importing scripts and manuscripts;
- structured screenplay editing;
- scene extraction;
- dialogue extraction;
- character-presence detection;
- location and prop discovery;
- time-of-day extraction;
- asset requirement proposals;
- continuity entry and exit state proposals;
- scene complexity estimation;
- breakdown approval.

### 9.2 Required modules

```text
Script Editor
Script Importer
Narrative Parser
Scene Breakdown Manager
Dialogue Register
Entity Extraction Service
Production Requirement Extractor
```

### 9.3 Human control

Automated breakdown results must remain proposals until reviewed and approved.

## 10. Production Planning

### 10.1 Required capabilities

VSCS must support:

- production scheduling;
- shot and scene priority;
- dependency planning;
- readiness planning;
- estimated render duration;
- resource and model availability;
- estimated storage usage;
- estimated processing cost;
- production milestones;
- blocked-work reporting;
- work status dashboards.

### 10.2 Required modules

```text
Production Planner
Dependency Planner
Readiness Dashboard
Production Schedule Manager
Cost and Runtime Estimator
Milestone Manager
```

## 11. Asset Management

### 11.1 Required capabilities

The Asset Manager must support the full object lifecycle:

- create;
- inspect;
- edit;
- duplicate;
- search;
- filter;
- categorise;
- tag;
- approve;
- archive;
- controlled deletion;
- variant creation;
- usage inspection;
- dependency inspection;
- version history.

### 11.2 Asset categories

At minimum:

- characters;
- locations;
- environments;
- ships;
- vehicles;
- props;
- costumes;
- creatures;
- technology;
- effects;
- camera profiles;
- lighting profiles;
- voices;
- audio profiles;
- music themes;
- interfaces;
- organisations.

### 11.3 Required modules

```text
Asset Manager
Asset Editor
Asset Browser
Asset Variant Manager
Asset Usage Inspector
Asset Dependency Inspector
Asset Approval Service
```

### 11.4 Required UI standard

Users must not need to memorise Asset IDs. All asset-consuming editors must provide browse and selection functions.

## 12. CAP and Canonical Reference Management

### 12.1 Required capabilities

VSCS must support:

- CAP creation and editing;
- CAP versioning;
- CAP approval and locking;
- CAP supersession;
- canonical descriptions;
- visual identity;
- dimensions, materials, colours, movement, and behavior;
- production restrictions;
- forbidden interpretations;
- canonical reference import;
- primary, secondary, and supplementary roles;
- reference approval and locking;
- reference previews;
- multiple canonical viewpoints;
- readiness validation;
- dependency checksums.

### 12.2 Required modules

```text
CAP Manager
CAP Editor
Canonical Reference Manager
Reference Previewer
CAP Approval Workflow
Canonical Readiness Service
Canonical Dependency Service
```

### 12.3 Help requirement

The CAP and Canonical Reference windows must include contextual help, field guidance, readiness information, and the recommended next workflow step.

## 13. Physical Reality and Plausibility

### 13.1 Required capabilities

VSCS must support the Physical Reality Framework through:

- project scientific rules;
- universal physical baselines;
- planetary and environmental profiles;
- gravity;
- atmosphere;
- pressure;
- temperature;
- radiation;
- material properties;
- human capability limits;
- vehicle dynamics;
- propulsion constraints;
- technology constraints;
- energy and heat constraints;
- weapon behavior;
- structural constraints;
- physical overrides;
- physical validation results.

### 13.2 Required modules

```text
VSCS Physics Engine (VPE)
Physical Rule Manager
Environment Profile Manager
Planet Profile Manager
Technology Profile Manager
Vehicle Physics Manager
Human Capability Manager
Physics Override Manager
Physics Validation Service
Prompt Physics Injector
Physics QC Service
```

### 13.3 Initial implementation policy

The first VPE implementation should be rule-based and profile-driven. Full numerical simulation is not required for v1.

### 13.4 Blocking examples

VSCS must be able to block or warn about:

- atmosphere-dependent effects in vacuum;
- impossible acceleration or deceleration;
- motion inconsistent with local gravity;
- invalid engine placement;
- unprotected humans in hostile environments;
- unsupported technology behavior;
- unlimited energy, strength, ammunition, or invulnerability without canon support.

## 14. Continuity Management

### 14.1 Required capabilities

VSCS must support:

- continuity states;
- continuity transitions;
- inheritance from canon, scene, shot, and previous approved output;
- character appearance, costume, injury, emotion, position, and equipment;
- asset configuration and damage;
- location and environmental state;
- camera direction;
- lighting direction;
- audio environment;
- start-frame and end-frame references;
- continuity conflict detection;
- cross-scene and cross-episode continuity;
- intentional override approval;
- continuity impact reporting.

### 14.2 Required modules

```text
Continuity Manager
Continuity State Editor
Continuity Transition Manager
Continuity Graph
Continuity Conflict Service
Continuity Inheritance Service
Continuity Override Manager
```

### 14.3 Required user view

The application should provide a dedicated Continuity View showing:

- inherited state;
- current state;
- state changes;
- following-state requirements;
- conflicts;
- affected shots.

## 15. Shot Planning and Previsualisation

### 15.1 Required capabilities

The Shot Planner must support:

- shot purpose;
- shot size;
- angle;
- lens;
- camera movement;
- blocking;
- composition;
- duration;
- dialogue;
- required assets;
- lighting;
- effects;
- physical constraints;
- continuity source and destination;
- storyboard references;
- status and approval;
- shot duplication and reordering;
- shot variants;
- clip subdivision.

### 15.2 Previsualisation capabilities

VSCS should support:

- storyboard generation;
- storyboard import;
- animatic creation;
- temporary voice tracks;
- camera and blocking preview;
- shot-duration preview;
- initial scene assembly.

### 15.3 Required modules

```text
Shot Planner
Blocking Planner
Camera Planner
Lighting Planner
Storyboard Manager
Animatic Builder
Previsualisation Review Workspace
```

## 16. ACPP Production Packaging

### 16.1 Required capabilities

The ACPP Editor must support:

- narrative intent;
- visual intent;
- complete asset bindings;
- CAP and reference resolution;
- camera and lighting;
- movement and blocking;
- dialogue and voice;
- audio requirements;
- continuity inputs and outputs;
- physical reality constraints;
- effects;
- renderer preference;
- workflow preference;
- quality target;
- output specification;
- dependency inventory;
- readiness validation;
- versioning and approval.

### 16.2 Required modules

```text
ACPP Editor
ACPP Builder
ACPP Validator
ACPP Version Manager
ACPP Readiness Service
ACPP Dependency Resolver
```

### 16.3 Automation

The system should automatically inherit and inject approved information, but the user must retain control over shot-specific intent.

## 17. Prompt Graph and Prompt Compilation

### 17.1 Required capabilities

VSCS must support:

- Prompt Graph construction;
- node and edge validation;
- asset enrichment;
- CAP and reference enrichment;
- continuity enrichment;
- physical reality enrichment;
- graph snapshots;
- graph differencing;
- provenance;
- renderer-neutral structure;
- renderer-specific compilation;
- positive and negative prompt separation;
- mandatory-detail protection;
- renderer profile selection;
- prompt optimisation;
- batch compilation;
- incremental compilation;
- reporting;
- recovery.

### 17.2 Required modules

```text
Prompt Graph Builder
Prompt Graph Resolver
Prompt Graph Validator
Prompt Graph Snapshot Service
Prompt Graph Difference Service
Prompt Compiler
Renderer Prompt Profile Manager
Prompt Optimisation Service
Batch Compilation Scheduler
Compilation History and Recovery
```

### 17.3 Critical guarantee

Prompt optimisation must never remove mandatory canonical, continuity, physical reality, safety, or production constraints.

## 18. Renderer and Workflow Management

### 18.1 Required capabilities

VSCS must support:

- renderer-neutral production packages;
- renderer registration;
- ComfyUI adapter support;
- workflow manifests;
- workflow discovery;
- workflow validation;
- model and node compatibility;
- quality-profile compatibility;
- continuity capability declarations;
- lip-sync capability declarations;
- resource validation;
- versioned workflow identities;
- diagnostics;
- reference workflows.

### 18.2 Required modules

```text
Renderer Registry
Renderer Adapter Framework
ComfyUI Adapter
Workflow Manifest Manager
Workflow Discovery Service
Workflow Compatibility Validator
Model Resource Registry
Workflow Diagnostics Viewer
```

## 19. Render Queue and Media Generation

### 19.1 Required capabilities

VSCS must support:

- preview generation;
- production generation;
- render submission;
- render queue management;
- job priority;
- concurrency limits;
- progress tracking;
- cancellation;
- retry;
- failure isolation;
- recovery checkpoints;
- restart recovery;
- output registration;
- renderer logs;
- seed policies;
- start and end frame control;
- versioned outputs;
- preview versus production profiles;
- batch generation.

### 19.2 Required modules

```text
Production Render Workspace
Render Queue Manager
Render Scheduler
Render Job Service
ComfyUI Execution Service
Render Progress Monitor
Render Recovery Service
Render Output Registry
Render Log Viewer
```

### 19.3 User requirements

The user must be able to see:

- queued jobs;
- running jobs;
- progress;
- current shot;
- failures;
- retry status;
- completed outputs;
- awaiting approvals.

## 20. Voice, Dialogue, Audio, and Lip-sync

### 20.1 Dialogue capabilities

VSCS must support:

- dialogue lines;
- dialogue segments;
- speaker assignment;
- voice profiles;
- pronunciation dictionaries;
- emotional direction;
- timing targets;
- generation and import;
- versioning;
- loudness normalisation;
- dialogue review.

### 20.2 Audio capabilities

VSCS must support:

- ambience;
- effects;
- foley;
- music;
- narration;
- machinery and vehicle sounds;
- audio profiles;
- audio stems;
- scene audio continuity;
- audio QC.

### 20.3 Lip-sync capabilities

VSCS must support:

- speaker-to-face mapping;
- single and multi-speaker modes;
- dialogue alignment;
- face tracking;
- identity preservation;
- lip-sync quality profiles;
- close-up precision modes;
- output review;
- retry and alternate processing.

### 20.4 Required modules

```text
Dialogue Manager
Voice Profile Manager
Voice Generation Service
Pronunciation Manager
Audio Asset Manager
Sound Design Workspace
Music Cue Manager
Audio Mix Service
Lip-sync Manager
Lip-sync Execution Service
Lip-sync Review Workspace
```

## 21. Quality Control and Review

### 21.1 Required capabilities

VSCS must support structured review for:

- concept;
- story;
- script;
- assets;
- CAPs;
- canonical references;
- shot plans;
- ACPPs;
- Prompt Graphs;
- previews;
- production renders;
- dialogue;
- lip-sync;
- sound;
- scenes;
- final productions;
- deliverables.

### 21.2 Review outcomes

```text
Approved
Approved with Notes
Revision Required
Rejected
```

### 21.3 Required modules

```text
Review Manager
Approval Service
Revision Request Manager
QC Checklist Manager
Automated Technical QC
Visual QC Workspace
Audio QC Workspace
Final QA Workspace
```

### 21.4 Required quality views

The system should expose:

- readiness;
- blocking errors;
- warnings;
- pending reviews;
- failed QC;
- revision requests;
- approval history.

## 22. Timeline, Assembly, and Post-production

### 22.1 Required capabilities

VSCS must support:

- scene timelines;
- episode timelines;
- film timelines;
- trailer timelines;
- video and audio tracks;
- timeline items;
- shot placement;
- trimming;
- transitions;
- dialogue alignment;
- music placement;
- titles;
- captions;
- subtitles;
- credits;
- proxies;
- scene and production versions;
- missing-shot detection;
- initial automatic assembly;
- export to external editors where required.

### 22.2 Post-production capabilities

VSCS should support or integrate with:

- colour grading;
- audio mixing;
- artifact cleanup;
- visual-effects finishing;
- title design;
- subtitle and caption generation;
- final mastering.

### 22.3 Required modules

```text
Timeline Editor
Scene Assembly Manager
Episode and Film Assembly Manager
Trailer Assembly Manager
Title and Credit Manager
Subtitle and Caption Manager
Post-production Workspace
External Editor Integration
```

## 23. Delivery, Distribution, and Archive

### 23.1 Deliverable capabilities

VSCS must support:

- production masters;
- streaming masters;
- review copies;
- trailers;
- teasers;
- promotional clips;
- social-media variants;
- vertical formats;
- subtitles and captions;
- metadata packages;
- delivery manifests;
- platform presets;
- output validation.

### 23.2 Distribution capabilities

VSCS should support:

- publication metadata;
- platform targets;
- scheduled release records;
- publication status;
- external links;
- release tracking.

### 23.3 Archive capabilities

VSCS must support:

- production manifests;
- source data;
- assets and CAPs;
- references;
- ACPPs;
- Prompt Graphs;
- prompts;
- workflows;
- render outputs;
- audio;
- timelines;
- final masters;
- checksums;
- archive verification;
- restore testing.

### 23.4 Required modules

```text
Deliverable Manager
Export Manager
Platform Preset Manager
Distribution Record Manager
Archive Manager
Archive Verification Service
Restore Service
```

## 24. Platform Services and Governance

### 24.1 Required shared services

```text
Identity and ID Service
Versioning Service
Audit Service
Dependency Service
Invalidation Service
Notification Service
Configuration Service
Storage Service
Media Registry
Search Service
Help and Guidance Service
Permission and Role Service
Plugin Manager
Telemetry and Diagnostics Service
```

### 24.2 Versioning

Every significant production object must support:

- version number;
- previous version;
- created and modified timestamps;
- author and modifier;
- change reason;
- approval state;
- supersession;
- dependency checksums.

### 24.3 Audit

Significant actions must produce audit events, including:

- create;
- edit;
- delete;
- archive;
- approve;
- unlock;
- supersede;
- compile;
- render;
- invalidate;
- retry;
- export.

### 24.4 Notifications

The system must notify users about:

- missing dependencies;
- approval requirements;
- changed canonical data;
- invalidated shots;
- failed jobs;
- completed renders;
- revision requests;
- workflow incompatibilities;
- archive requirements.

## 25. Help and Workflow Guidance

### 25.1 Required capabilities

Every major window must provide an appropriate level of help.

The help system should support:

- window purpose;
- field guidance;
- workflow position;
- readiness checklist;
- validation explanations;
- recommended next action;
- links to related objects;
- examples;
- contextual troubleshooting.

### 25.2 Required modules

```text
Contextual Help Framework
Workflow Guidance Service
Readiness Checklist Service
Onboarding and Guided Tour Framework
Troubleshooting Knowledge Base
```

### 25.3 Priority windows

The following windows require formal help coverage:

- Project creation;
- Story and Scene editors;
- Shot Planner;
- Asset Manager;
- CAP Manager;
- Canonical Reference Manager;
- ACPP Editor;
- Prompt Preview;
- Production Render Workspace;
- Voice and Lip-sync workspaces;
- QC and Timeline workspaces.

## 26. Workflow Navigation

### 26.1 Required capability

VSCS must expose a clear production path rather than a collection of unrelated screens.

The application should provide:

- a production workflow navigator;
- current stage;
- completed stages;
- blocked stages;
- optional stages;
- recommended next task;
- direct navigation to blockers;
- return navigation to the owning production object.

### 26.2 Required module

```text
Production Workflow Navigator
```

### 26.3 Example

```text
Scene approved
→ 3 assets missing CAPs
→ Open CAP Manager
→ Approve references
→ Return to Shot Planner
→ Build ACPP
```

## 27. Capability Dependency Map

The primary dependency sequence is:

```text
Project Management
→ Story and Canon
→ Production Structure
→ Script Breakdown
→ Asset Registry
→ CAP and References
→ Physical Reality Profiles
→ Continuity States
→ Shot Planning
→ ACPP
→ Prompt Graph
→ Prompt Compilation
→ Workflow Resolution
→ Preview Rendering
→ Preview Approval
→ Production Rendering
→ Voice and Lip-sync
→ Shot QC
→ Timeline Assembly
→ Final QA
→ Deliverables
→ Archive
```

A capability may be implemented early, but it cannot be considered production-complete until its upstream dependencies are available.

## 28. Minimum Viable End-to-End Production Path

The minimum v1 path required to create a complete trailer or short production is:

```text
Project
Production
Story or Script
Scene
Shot
Clip
Asset
CAP
Canonical Reference
Physical Environment Profile
Continuity State
ACPP
Prompt Graph
Compiled Prompt Package
Workflow Manifest
Preview Render Job
Preview Review
Production Render Job
Render Output
Dialogue and Voice Output
Lip-sync Output
Shot Review
Timeline
Deliverable
Archive Record
```

## 29. Capability Priority Classification

### 29.1 Foundation

Required before production execution:

- Project and production hierarchy;
- Story and canon;
- Asset Manager;
- CAP and canonical references;
- continuity;
- Physical Reality profiles;
- Shot Planner;
- ACPP;
- Prompt Graph;
- Prompt Compiler;
- workflow manifests.

### 29.2 Production-critical

Required to generate completed media:

- render queue;
- ComfyUI execution;
- preview and production profiles;
- output registry;
- review and approval;
- voice generation;
- lip-sync;
- shot QC;
- timeline assembly;
- deliverable export.

### 29.3 Operational maturity

Required for reliable sustained production:

- recovery;
- dependency invalidation;
- progress and reporting;
- versioning;
- audit;
- notifications;
- archive;
- help and workflow guidance.

### 29.4 Advanced

Can follow after v1:

- numerical physics assistance;
- advanced visual identity scoring;
- distributed rendering;
- predictive scheduling;
- automatic edit suggestions;
- direct publishing integrations;
- multi-user production roles.

## 30. Current Architecture Compatibility Principle

The current VSCS implementation must not be assumed to define the target capability map.

During Phase 17.6.2, each existing feature will be classified as:

```text
Aligned
Partially Aligned
Incomplete
Duplicated
Obsolete
Unreachable
Missing
Requires Redesign
```

The target capabilities in this document remain authoritative even when the current implementation differs.

## 31. Phase 17.6.2 Input Matrix

This capability map provides the comparison baseline for the Functional Gap Analysis.

For every capability, Phase 17.6.2 must record:

- required capability;
- current implementation status;
- current module or window;
- functional completeness;
- UI accessibility;
- edit lifecycle completeness;
- help coverage;
- continuity integration;
- quality integration;
- automation integration;
- Physical Reality integration;
- required action;
- priority;
- recommended phase.

## 32. Required Future Production Workspaces

The final application should provide the following major workspaces:

```text
Home and Project Workspace
Concept and Story Workspace
Canon and World Workspace
Production Structure Workspace
Script and Breakdown Workspace
Asset and CAP Workspace
Physical Reality Workspace
Continuity Workspace
Shot Planning Workspace
ACPP and Prompt Workspace
Production Render Workspace
Voice and Audio Workspace
QC and Review Workspace
Timeline and Post-production Workspace
Delivery and Archive Workspace
```

These workspaces may contain several panels or editors but should present one coherent workflow.

## 33. Capability Acceptance Principles

A capability is not complete merely because a service or data model exists.

A capability is complete only when:

1. The object can be created.
2. The object can be viewed.
3. The object can be edited where lifecycle rules permit.
4. The object can be searched or browsed.
5. The object can be validated.
6. The object exposes its status and dependencies.
7. The object participates in continuity, quality, automation, and physical reality where relevant.
8. The function is accessible from the intended workflow.
9. Contextual help exists where needed.
10. Automated and manual tests certify the capability.

## 34. Phase Deliverables

Phase 17.6.1.4 formally delivers:

- Required VSCS Capability Map;
- Capability Domain Register;
- Required Module Catalogue;
- Workflow Navigation Requirements;
- Platform Service Register;
- Minimum Viable Production Path;
- Capability Priority Classification;
- Capability Acceptance Principles;
- Functional Gap Analysis Input Matrix;
- Future Production Workspace Model.

## 35. Expected Outcome

At the completion of Phase 17.6.1.4, VSCS has a definitive description of the complete software platform required to produce a film, series, episode, short film, trailer, teaser, or promotional video from initial idea through final archived deliverable.

The specification establishes:

- what modules VSCS must contain;
- what each module must do;
- how modules fit into the production workflow;
- where continuity is enforced;
- where quality is measured;
- what automation is safe;
- how physical reality is represented and validated;
- which human approvals are mandatory;
- which capabilities are essential for v1;
- how the existing application must be assessed.

The next phase is:

# Phase 17.6.2 — Functional Gap Analysis

Phase 17.6.2 will compare this required capability map with the actual VSCS repository and user interface, identify missing, obsolete, incomplete, duplicated, or inaccessible functionality, and produce the prioritised consolidation roadmap.