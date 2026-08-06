Revised Production MVP Implementation Sequence
Stage 1 — Story Foundation (P0)

This stage enables the creator to transform an idea into an approved Story Canon.

Phase 18.1 — Story Workspace Foundation

Implement:

Story Workspace
Story navigation
Story lifecycle
Story metadata
Story editor integration
Story versioning
Story Help

Outcome

The Story becomes the primary object immediately beneath the Project.

Phase 18.2 — Story Analysis

Implement:

Story import
Story parser
Story analysis
Character extraction
Location extraction
Prop extraction
Dialogue extraction
Timeline extraction
Suggested Episodes
Suggested Scenes

Outcome

VSCS automatically proposes a production structure from the imported story.

Phase 18.3 — Story Definition and Approval

Implement:

Story review
Canon approval
Character approval
Location approval
Timeline approval
Story version locking

Outcome

Approved Story Canon.

Stage 2 — Production Foundation (P0)

Once the Story has been approved, production can begin.

Phase 19.1 — Production Lifecycle Foundation

Implement:

Production object
Production lifecycle
Production metadata
Production settings
Production types
Production dashboard
Production Help

Outcome

Multiple productions can be created from one Story.

Phase 19.2 — Production Structure

Implement:

Episodes
Sequences
Scenes
Shots
Clips (optional)
Reordering
Runtime calculations

Outcome

Complete production hierarchy.

Stage 3 — Asset Foundation (P0)

Most of this already exists.

The focus is completing missing lifecycle functionality.

Phase 20.1

Asset lifecycle completion.

Phase 20.2

CAP workflow.

Phase 20.3

Canonical References.

Phase 20.4

Asset Readiness.

Stage 4 — Production Planning (P0)

This becomes a dedicated stage rather than being mixed with Story planning.

Phase 21.1

Scene Planning.

Phase 21.2

Shot Planning.

Phase 21.3

Production Readiness Engine.

Phase 21.4

Dependency Planning.

Phase 21.5

Executable Production Plan.

Stage 5 — Prompt Production (P0)

Reuse the work we've already completed.

Phase 22.1

ACPP generation.

Phase 22.2

Prompt Graph.

Phase 22.3

Prompt optimisation.

Phase 22.4

Batch compilation.

Phase 22.5

Prompt validation.

Stage 6 — Rendering (P0)
Phase 23.1

Preview rendering.

Phase 23.2

Preview review.

Phase 23.3

Production rendering.

Phase 23.4

Recovery.

Phase 23.5

Render history.

Stage 7 — Audio Production (P0)
Phase 24.1

Dialogue.

Phase 24.2

Voice assignment.

Phase 24.3

Lip-sync.

Phase 24.4

Sound.

Phase 24.5

Music.

Stage 8 — Quality Control (P0)
Phase 25.1

Shot QC.

Phase 25.2

Scene QC.

Phase 25.3

Production QC.

Phase 25.4

Physical Reality validation.

Phase 25.5

Continuity validation.

Stage 9 — Timeline and Delivery (P0)
Phase 26.1

Timeline.

Phase 26.2

Automatic assembly.

Phase 26.3

Mastering.

Phase 26.4

Export.

Phase 26.5

Release.

Updated Production MVP Critical Path
Project
    │
    ▼
Story
    │
    ▼
Story Analysis
    │
    ▼
Story Approval
    │
    ▼
Production
    │
    ▼
Production Structure
    │
    ▼
Assets
    │
    ▼
CAPs
    │
    ▼
Scenes
    │
    ▼
Shots
    │
    ▼
Production Planning
    │
    ▼
Prompt Production
    │
    ▼
Preview Rendering
    │
    ▼
Production Rendering
    │
    ▼
Dialogue
    │
    ▼
Lip-sync
    │
    ▼
Quality Control
    │
    ▼
Timeline
    │
    ▼
Mastering
    │
    ▼
Release
Updated P0 Backlog

This becomes the implementation backlog for the Production MVP:

Priority	Phase	Status
P0	18.1 Story Workspace Foundation	Planned
P0	18.2 Story Analysis	Planned
P0	18.3 Story Definition and Approval	Planned
P0	19.1 Production Lifecycle Foundation	Planned
P0	19.2 Production Structure	Planned
P0	20.1 Asset Lifecycle Completion	Partial
P0	20.2 CAP Workflow	Partial
P0	20.3 Canonical References	Partial
P0	20.4 Asset Readiness	Planned
P0	21.1 Scene Planning	Partial
P0	21.2 Shot Planning	Partial
P0	21.3 Production Readiness	Planned
P0	21.4 Dependency Planning	Planned
P0	21.5 Executable Production Plan	Planned
P0	22.1–22.5 Prompt Production	Foundation Complete
P0	23.1–23.5 Rendering	Partial
P0	24.1–24.5 Audio Production	Planned
P0	25.1–25.5 Quality Control	Planned
P0	26.1–26.5 Timeline and Delivery	Planned
Recommendation

I recommend saving this as a new engineering document:

docs/engineering/VSCS_Production_MVP_Roadmap_v2.md

rather than editing the existing roadmap in place.

The original roadmap remains a record of how the project evolved, while Version 2 becomes the operational roadmap that matches the approved VSCS Video Production Workflow V2. From this point onward, that roadmap should be the only backlog we use to drive implementation, ensuring every completed phase moves us directly toward producing the Xorix trailer and, ultimately, the Xorix streaming series.