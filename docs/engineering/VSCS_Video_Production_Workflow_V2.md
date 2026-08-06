# Video Series Studio (VSCS)
# Video Production Workflow

---

| Document Information | |
|----------------------|------------------------------------------------|
| **Document ID** | VSCS-WF-002 |
| **Title** | VSCS Video Production Workflow |
| **Version** | 2.0 |
| **Status** | Active Engineering Baseline |
| **Owner** | VSCS Development Team |
| **Primary Architect** | Neill Payne |
| **Engineering Partner** | OpenAI ChatGPT |
| **Repository** | https://github.com/npayne10/video_series_studio |
| **Supersedes** | VSCS_Video_Production_Workflow.md (Version 1.0) |

---

# Revision History

| Version | Description |
|----------|-------------|
| 1.0 | Initial production workflow |
| 2.0 | Story-Driven Production workflow. Story becomes the canonical source of truth for all productions. |

---

# 1. Purpose

This document defines the authoritative end-to-end workflow for producing cinematic video content using Video Series Studio (VSCS).

Version 2.0 establishes a fundamental architectural principle:

> **Every production begins with a Story.**

The Story represents the creative truth.

Productions represent different executable interpretations of that Story.

One approved Story may therefore produce many independent Productions.

Examples include:

- Television Series
- Feature Film
- Trailer
- Character Showcase
- Marketing Video
- Social Media Campaign

---

# 2. Guiding Principles

The workflow follows these principles:

- Story drives production.
- Production never changes Story Canon.
- Canonical assets are reused whenever possible.
- Every production must maintain continuity.
- Physical Reality rules always apply.
- Automation supports creativity.
- Every stage produces structured information for the next stage.

---

# 3. High-Level Workflow

```text
Idea
    │
    ▼
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
CAPs & Canonical References
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
Prompt Generation
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
```

---

# Stage 1 — Story Development

## Step 1 — Create Project

A Project is the highest-level organisational container.

A Project contains:

- Stories
- Productions
- Assets
- CAPs
- Canonical References
- Audio
- Documentation
- Production History

### Output

Project created.

---

## Step 2 — Create or Import Story

The Story is the canonical creative source.

Supported inputs include:

- DOCX
- PDF
- Markdown
- Screenplay
- Plain text
- Story written directly inside VSCS

The Story remains independent of any Production.

### Output

Story Source.

---

## Step 3 — Story Analysis

VSCS analyses the Story and proposes:

- Characters
- Locations
- Planets
- Props
- Ships
- Vehicles
- Technology
- Dialogue
- Timeline
- Episodes
- Scenes
- Asset candidates
- Music opportunities
- Visual effects
- Continuity candidates

Analysis is advisory only.

Nothing becomes canonical until approved.

### Output

Structured Story Analysis.

---

## Step 4 — Story Definition and Approval

The author reviews and approves:

- Story structure
- Episodes
- Canon
- Characters
- Locations
- Timeline
- Dialogue
- Notes

The approved Story becomes Story Canon.

### Output

Approved Story Canon.

---

# Stage 2 — Production Planning

## Step 5 — Create Production

A Production is created from an approved Story.

Supported production types include:

- Television Series
- Episode
- Trailer
- Feature Film
- Short Film
- Promotional Video
- Social Media Clip

One Story may have many Productions.

Examples:

```text
Story

├── Trailer
├── Episode 1
├── Episode 2
├── Marketing Video
└── Character Introduction
```

Each Production defines:

- Runtime
- Resolution
- Aspect Ratio
- Frame Rate
- Renderer Profile
- Audio Profile
- Output Platform
- Production Status

### Output

Production Definition.

---

## Step 6 — Build Production Structure

The Production is organised into executable production objects.

Television Series:

```text
Production
    │
    ▼
Episode
    │
    ▼
Sequence
    │
    ▼
Scene
    │
    ▼
Shot
    │
    ▼
Clip (optional)
```

Trailer:

```text
Trailer
    │
    ▼
Beat
    │
    ▼
Scene
    │
    ▼
Shot
```

Scenes describe **what happens**.

Shots describe **how the audience experiences it**.

### Output

Approved Production Structure.

---

## Step 7 — Asset Planning

VSCS analyses every planned Shot and creates the required asset list.

For each asset the user may:

- Reuse existing asset
- Create new asset
- Create variant
- Leave unresolved

### Output

Asset Plan.

---

## Step 8 — Asset Creation

The Asset Manager creates and maintains:

- Characters
- Locations
- Props
- Ships
- Vehicles
- Technology
- Camera Profiles
- Lighting Profiles
- Audio Profiles

Every asset receives a permanent identifier.

### Output

Registered Assets.

---

## Step 9 — CAPs and Canonical References

Every reusable production asset receives:

- Approved CAP
- Canonical References
- Behaviour rules
- Physical Reality constraints
- Production restrictions

Only approved assets may enter production.

### Output

Production-ready Assets.

---

## Step 10 — Scene Planning

Every Scene defines:

- Narrative purpose
- Summary
- Location
- Time
- Characters
- Actions
- Dialogue
- Emotional intent
- Entry continuity
- Exit continuity
- Required assets

### Output

Approved Scenes.

---

## Step 11 — Shot Planning

Every Shot defines:

- Purpose
- Duration
- Camera
- Lens
- Camera movement
- Blocking
- Lighting
- Dialogue
- Required assets
- Effects
- Continuity
- Physical Reality constraints
- Renderer quality targets

### Output

Production-ready Shots.

---

## Step 12 — Production Planning

Production Planning transforms creative planning into an executable production plan.

For every Shot, VSCS validates:

- Asset readiness
- CAP readiness
- Canonical References
- Dialogue
- Voice assignments
- Camera
- Lighting
- Physical Reality
- Renderer compatibility
- Dependencies
- Render order
- Parallel execution
- Lip-sync requirements
- Audio requirements
- Output location

The resulting Production Plan contains:

- Production Order
- Dependency Graph
- Preview Queue
- Production Queue
- Audio Queue
- Lip-sync Queue
- Quality Control Queue
- Estimated render time
- Blocked work

### Output

Executable Production Plan.

---

# Stage 3 — Production Generation

## Step 13 — Build Production Packages

VSCS automatically generates an ACPP package for every approved Shot.

The package combines:

- Story intent
- Shot information
- Assets
- CAPs
- Canonical References
- Camera
- Lighting
- Dialogue
- Continuity
- Physical Reality
- Renderer settings

### Output

Renderer-neutral Production Package.

---

## Step 14 — Compile Prompt Packages

VSCS generates:

- Prompt Graph
- Positive Prompt
- Negative Prompt
- References
- Renderer Workflow
- Workflow Parameters
- Output Definition

### Output

Renderer-ready Package.

---

## Step 15 — Preview Rendering

Generate preview-quality renders for creative approval.

Review includes:

- Character identity
- Composition
- Camera
- Lighting
- Continuity
- Physical Reality
- Timing
- Prompt accuracy

### Output

Approved Preview.

---

## Step 16 — Production Rendering

Generate production-quality video.

VSCS manages:

- Queueing
- Progress
- Recovery
- Versioning
- Output registration

### Output

Production-quality Video Shots.

---

# Stage 4 — Post Production

## Step 17 — Dialogue and Lip-sync

Generate or import dialogue.

Assign voices.

Apply lip-sync.

Approve results.

### Output

Dialogue-complete Video Shots.

---

## Step 18 — Audio Production

Apply:

- Dialogue
- Ambience
- Foley
- Effects
- Music
- Narration

Audio continuity is maintained across adjoining shots.

### Output

Complete Audio Mix.

---

## Step 19 — Quality Control

Validate:

- Story accuracy
- Continuity
- Physical Reality
- Asset identity
- Motion quality
- Dialogue
- Lip-sync
- Audio
- Technical quality

Only approved shots continue.

### Output

Approved Production Shots.

---

## Step 20 — Timeline Assembly

Assemble:

- Video
- Dialogue
- Music
- Effects
- Titles
- Captions
- Credits

Create the first complete edit.

### Output

Production Timeline.

---

# Stage 5 — Delivery

## Step 21 — Mastering

Prepare the final production by applying:

- Colour grading
- Audio mastering
- Final quality review
- Platform validation
- Master encoding

### Output

Release Master.

---

## Step 22 — Export

Generate:

- Streaming Master
- Trailer
- Review Copy
- Social Media Versions
- Archive Package

### Output

Exported Deliverables.

---

## Step 23 — Release and Archive

Publish the production.

Record:

- Version
- Release destination
- Publication status
- Archive location
- Checksums

### Output

Published Production.

---

# Creative Workflow

```text
Idea
    │
    ▼
Story
    │
    ▼
Story Analysis
    │
    ▼
Story Approval
```

The Creative Workflow defines **what** is being told.

---

# Production Workflow

```text
Production
    │
    ▼
Planning
    │
    ▼
Generation
    │
    ▼
Post Production
    │
    ▼
Release
```

The Production Workflow defines **how** the approved Story is transformed into a finished production.

---

# Core Architectural Principle

One approved Story may generate multiple independent Productions.

Examples include:

- Television Series
- Feature Film
- Trailer
- Marketing Campaign
- Character Showcase

Each Production shares the same Story Canon while maintaining its own:

- Production Settings
- Timeline
- Render Profiles
- Deliverables
- Release History

---

# Conclusion

Video Series Studio is a **Story-Driven Production System**.

The Story remains the canonical source of truth throughout the lifecycle.

Every Production is an executable interpretation of that Story, allowing multiple productions to be created while maintaining continuity, quality, physical plausibility and creative consistency.

This workflow forms the authoritative operational model for all future VSCS development.
