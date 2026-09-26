# Phase 20.18.2.3.6 — Automated Introduction Boundary Synthesis & Span Orchestration

## Objective

Remove routine manual boundary-image authoring from dynamic timed-asset Shots while
preserving the frame-exact authority delivered by Phases 20.18.2.3.1 through 20.18.2.3.5.

The operator remains responsible for story authority and final visual acceptance. VSCS
is responsible for producing the intermediate technical evidence and provider work.

Normal production must therefore be:

```text
governed timed asset authority
        |
derive internal spans
        |
render SPAN-001
        |
extract exact final governed frame
        |
synthesize introduced asset(s) from canonical references
        |
register automated structural Introduction Keyframe
        |
render next governed span
        |
repeat for further boundaries
        |
assemble exact governed Shot
        |
human final visual QC
```

The Phase 20.18.2.3.5 manual Introduction Keyframe/package/assembly controls remain
available only as explicit recovery controls.

## Problem addressed

Phase 20.18.2.3.5 deliberately proved the safety boundary by asking the operator to
supply:

1. the preceding internal-boundary image; and
2. the target Introduction Keyframe.

That is suitable for functional acceptance but not normal episode production. Requiring
two manually prepared images at every in-Shot introduction would move production work
back to the operator and defeat VSCS automation.

Phase 20.18.2.3.6 makes both images system-produced:

- the source boundary is decoded directly from the normalized preceding span;
- the target Introduction Keyframe is synthesized from that exact boundary plus the
  governed canonical reference for the introduced asset.

## Provider-neutral strategy ladder

VSCS models three introduction strategies:

```text
DIRECT_PROVIDER_REFERENCE
    provider can inject the governed reference at the exact timed boundary

SYNTHESIZED_KEYFRAME
    VSCS generates the first emitted target-span frame automatically

MANUAL_FALLBACK
    explicit operator recovery when the provider cannot do either safely
```

For the current LTX-2.5 Candidate C path, the selected strategy is
`SYNTHESIZED_KEYFRAME`.

The strategy contract is provider-neutral so later providers may bypass image synthesis
when native timed-reference injection is proven reliable.

## SHT-002 reference case

Governed authority:

```text
Shot: EP-001-SCN-001-SHT-002
24 fps
144 frames

SPAN-001 = frames 0-95
SPAN-002 = frames 96-143

Boundary = 95 -> 96

Introduced asset:
CAP-CHR-005 Major Ros Rohsgard

Ros canonical reference:
LIVE-SECONDARY_IDENTITY-CAP-CHR-005
```

No operator-created frame 95 or frame 96 is required.

## Exact source-boundary extraction

After SPAN-001 completes and has been normalized to its governed 96 frames, VSCS decodes
its exact final frame:

```text
SPAN-001 local frame 95
        ==
SHT-002 global frame 95
```

The PNG is written under:

```text
.vscs/automated_introduction_boundaries/
    <shot>/
        <requirement>/
            source-frame-000095.png
```

The extracted file is checksum-pinned.

Assembly still proves that the approved/extracted boundary image matches the actual
decoded final frame of the preceding normalized span.

## Automated Introduction Keyframe synthesis

VSCS uses the existing Qwen Image Edit 2511 production stack.

The synthesis request contains:

- exact decoded preceding boundary frame;
- checksum of that boundary;
- governed introduced asset ID;
- exact governed canonical reference ID;
- canonical-reference path and checksum;
- target width and height;
- target global frame;
- current source Production Package fingerprint;
- deterministic seed;
- bounded positive and negative edit instructions.

The image-edit instruction is continuity-first:

```text
preserve existing camera
preserve existing framing
preserve lighting
preserve environment
preserve all existing people and objects
preserve identities/wardrobe/positions/scale
introduce only the governed canonical asset
do not duplicate or replace existing subjects
```

The dedicated workflow is:

```text
src/vscs/workflows/image/
    VSCS_Qwen_Introduction_Boundary_Workflow_API_v1.json
```

Its custom loader is:

```text
VSCSIntroductionBoundaryPackageLoaderV1
```

The loader checksum-verifies both source and canonical introduced reference before the
provider graph is allowed to run.

## Multiple simultaneous introductions

The request model supports multiple introduced canonical references.

The current Qwen implementation applies them as deterministic sequential image-edit
passes against the same evolving boundary frame:

```text
source boundary
    + introduced reference 1
        -> pass 1
    + introduced reference 2
        -> pass 2
    ...
        -> final target boundary
```

This avoids a fixed provider reference-slot ceiling while retaining checksum-pinned
provenance for every introduced asset.

## Structural automation versus semantic acceptance

Phase 20.18.2.3.4 originally described every Introduction Keyframe as human-approved.

Phase 20.18.2.3.6 distinguishes:

```text
approval_mode = human
approval_mode = automated_structural
```

An `automated_structural` Introduction Keyframe may condition the next provider span
only after machine-verifiable evidence confirms:

- source boundary checksum;
- introduced canonical-reference checksums;
- output geometry;
- current governed requirement identity.

This does **not** claim that machine checks have semantically proven character presence,
identity quality or visual continuity.

Those visual acceptance criteria remain at the assembled-Shot QC gate:

1. introduced asset absent before the boundary;
2. introduced asset present from target frame;
3. source visual continuity preserved;
4. no unapproved asset introduced.

This separation allows automation without weakening human production acceptance.

## Internal span provider orchestration

`LTX25AutomatedSpanProvider` executes isolated Candidate C span packages directly
through the existing ComfyUI provider adapter.

Internal spans are implementation detail beneath one editorial ProductionTask.

Phase 20.18.2.3.6 does not create:

- another ProductionTask for each span;
- another ProductionQueue entry for each span;
- another governed retry attempt for each span.

The existing editorial Shot remains the retry/queue authority.

Provider model memory is released between video and image synthesis stages where
possible.

## Incremental package materialization

The Phase 20.18.2.3.5 package builder previously required every Introduction Keyframe
before it could emit any span package.

Phase 20.18.2.3.6 adds incremental materialization:

```text
build(..., through_sequence=1)
build(..., through_sequence=2)
...
```

This lets VSCS render SPAN-001 before the frame-96 Introduction Keyframe exists.

Once frame 96 is synthesized and registered, SPAN-002 can be materialized and executed.

## Resumability and stale-artifact handling

Automated orchestration persists checksum-pinned span completion state in:

```text
.vscs/automated_span_orchestration_state.json
```

A previously completed span is reused only when all of the following still match:

- current Production Package fingerprint;
- governed span identity and sequence number;
- current generated span-package checksum;
- persisted provider-output path;
- persisted provider-output checksum.

If any check fails, that span is rerendered. Later spans may still be reused only if their
own current package checksum and output checksum remain valid.

Introduction Keyframe reuse has an additional boundary rule: the registered keyframe's
`source_boundary_image_sha256` must equal the exact frame decoded from the current
(reused or rerendered) preceding span. If it differs, VSCS regenerates the Introduction
Keyframe and the changed conditioning package naturally invalidates the affected later
span.

This gives re-entry a fail-closed "resume from the first stale point" behaviour without
creating another ProductionTask retry.

## Output assembly

The existing Phase 20.18.2.3.5 exact assembly runtime remains authoritative.

For SHT-002:

```text
SPAN-001
96 governed frames
LTX provider request = 97
normalized output = 96

SPAN-002
48 governed frames
LTX provider request = 49
normalized output = 48

assembled Shot = 144 frames at 24 fps
```

The provider-generated extra frame is never allowed into governed assembly.

## Production Execution UI

The timed-span panel now presents:

```text
Run Automated Span Orchestration
```

as the normal dynamic-Shot action.

It runs on a worker thread so long provider work does not block the desktop UI.

The former Phase 3.5 actions remain visible and are renamed as manual recovery controls:

- Build Span Packages — Manual Recovery
- Approve Introduction Keyframe — Manual Recovery
- Verify & Assemble Span Outputs — Manual Recovery

`Record Visual QC` remains the final explicit human acceptance gate.

The ordinary monolithic `Start Production` remains disabled for dynamic multi-span
Shots.

## Runtime audit

Automated synthesis authority is recorded in:

```text
.vscs/automated_introduction_boundaries.json
```

Generated source/target images are retained under:

```text
.vscs/automated_introduction_boundaries/<shot>/<requirement>/
```

Orchestration events are append-only in:

```text
.vscs/automated_span_orchestration.json
```

The final assembled Shot is written beneath the configured managed media directory,
defaulting to:

```text
Media Output/Automated Spans/<shot>/
```

## Failure policy

Automation fails closed.

Provider failure, missing files, checksum mismatch, changed source authority, invalid
geometry, missing canonical references, stale Introduction Keyframe requirements, invalid
span topology or failed assembly stops orchestration.

No failure:

- resets retry authority;
- edits ProductionTask JSON directly;
- invents a canonical reference;
- converts a failed synthesis into accepted authority;
- invokes monolithic dynamic-Shot execution.

The operator may then use the explicit Phase 3.5 recovery controls.

## ComfyUI deployment

Deploy the Phase 3.6 loader with:

```powershell
.\scripts\deploy_comfyui_introduction_boundary_v1.ps1
```

Default ComfyUI root:

```text
D:\ComfyUI1\ComfyUI_windows_portable\ComfyUI
```

Restart ComfyUI after deployment.

## Functional acceptance target

With SHT-002 compiled in `KEYFRAME_REQUIRED`:

1. click **Run Automated Span Orchestration**;
2. no image-selection dialog appears;
3. SPAN-001 is generated;
4. exact frame 95 is extracted automatically;
5. Qwen synthesizes frame 96 using the governed Ros reference;
6. the structural Introduction Keyframe is registered automatically;
7. SPAN-002 is generated from frame 96;
8. both normalized span outputs are assembled to exactly 144 frames;
9. state becomes `QC_REQUIRED`;
10. the operator reviews the final 95 -> 96 transition and records visual QC;
11. state becomes `ACCEPTED` only if all visual criteria pass.

## Deliberate exclusions

This phase does not yet implement:

- autonomous vision-based semantic acceptance of identity/continuity;
- silent auto-acceptance of final visual QC;
- provider-specific direct timed-reference injection for providers not yet validated;
- ProductionTask retry resets or extensions;
- hidden child ProductionTasks;
- automatic promotion of the assembled Shot to approved Generated Media.

Those remain separate governed decisions.
