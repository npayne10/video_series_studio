# Phase 20.18.2.3.5 — UI, QC and Functional Acceptance

## Purpose

Phase 20.18.2.3.5 closes the governed timed-asset-introduction capability line by
making the accepted Phase 20.18.2.3.1–3.4 authority visible and usable from Production
Execution, and by recording explicit functional-acceptance evidence for the resulting
dynamic Shot.

The phase does **not** redefine one editorial Shot as multiple ProductionTasks.

It also does **not** bypass existing ProductionQueue, lease, retry, or Generated Media
authority.

For dynamic timed-span Shots, the normal monolithic **Start Production** path remains
blocked. Instead, VSCS creates isolated Candidate C acceptance packages for the governed
internal spans. Those packages can be exercised during controlled functional acceptance
without consuming or rewriting the ProductionTask's production retry history.

## Accepted Ros case

The acceptance case remains:

```text
SHT-002
24 fps
144 governed frames

SPAN-001
global 0–95
96 governed frames
Ros absent

boundary
source global 95
target global 96

SPAN-002
global 96–143
48 governed frames
Ros present from frame 96
```

Provider geometry remains:

```text
SPAN-001  96 governed -> 97 LTX-2.5 provider -> normalized to 96
SPAN-002  48 governed -> 49 LTX-2.5 provider -> normalized to 48

final assembled Shot = 96 + 48 = 144 governed frames
```

Frame 95 is continuity evidence only.

Frame 96 is the approved Governed Introduction Keyframe and the first emitted frame of
SPAN-002.

The preceding frame is never duplicated into the target span.

## Production Execution UI

The Production Execution workspace now contains a
**Timed Asset / Span Functional Acceptance** section.

It displays:

- number of governed internal spans;
- number of internal boundaries;
- Introduction Keyframe approvals;
- visual-QC approvals;
- assembly state;
- exact final frame count;
- current functional-acceptance state.

The state machine is:

```text
PACKAGE_REQUIRED
    |
KEYFRAME_REQUIRED
    |
OUTPUTS_REQUIRED
    |
QC_REQUIRED
    |
ACCEPTED
```

Static / monolithic Shots report `NOT_APPLICABLE` and retain their existing Production
Execution behavior.

### Operator controls

The workspace exposes:

- **Approve Introduction Keyframe**
- **Build Span Packages**
- **Verify & Assemble Span Outputs**
- **Record Visual QC**

The ordinary **Start Production** button is disabled whenever the selected compiled Shot
contains multiple governed internal spans.

This prevents the existing monolithic provider path from silently ignoring timed-span
authority.

## Cross-Shot opening continuity

Live SHT-002 acceptance exposed a boundary-authority gap between the Phase 19 Continuity
Compiler and Phase 20.18.2.2i Shot Boundary Keyframes.

An explicit preservation directive such as:

```text
Continue directly from EP-001-SCN-001-SHT-001.
```

now compiles deterministic boundary authority:

```text
shot_boundary_mode = continuous
source_shot_id = EP-001-SCN-001-SHT-001
```

This is not inferred from sequence position alone. The current Shot must explicitly name
the predecessor and use a preservation directive. Otherwise the fail-safe mode remains
`new_composition`.

For SHT-002 this ensures the published SHT-001 closing boundary is the governed opening
continuity source for SPAN-001 rather than silently falling back to an independent
composition.

## Introduction Keyframe approval

The operator selects:

1. the approved target Introduction Keyframe;
2. the exact preceding internal-boundary image;
3. the approving human identity.

The existing Phase 20.18.2.3.4 keyframe authority remains authoritative.

Both images are checksum-pinned.

The approved source-boundary image is no longer accepted merely because it exists. During
span-output assembly, Phase 20.18.2.3.5 decodes the exact final frame of the preceding
normalized span and compares its RGB pixel hash with the approved source-boundary image.

For the Ros case this proves:

```text
approved source-boundary image
        ==
actual normalized SPAN-001 local frame 95
        ==
SHT-002 global frame 95
```

A mismatch blocks assembly acceptance.

## Candidate C span acceptance packages

After all required Introduction Keyframes are approved, VSCS can build one executable
Candidate C package per governed internal span.

Packages are materialized under:

```text
.vscs/timed_span_acceptance/packages/<task>/<profile>/
    span-001.json
    span-002.json
    ...
```

These are functional-acceptance artifacts. Building them does not create a ProductionQueue
attempt and does not consume retry authority.

### SPAN-001 package

The first span uses the governed Shot opening keyframe.

For the Ros case:

```text
global_start_frame  = 0
global_through_frame = 95
governed_frame_count = 96
provider_frame_count = 97
provider_trim_frames = 1
```

Its bounded motion instruction explicitly preserves the approved active subjects and
forbids introducing a new subject.

### Later span packages

Each later span uses its approved Governed Introduction Keyframe.

For SPAN-002:

```text
global_start_frame = 96
global_through_frame = 143
governed_frame_count = 48
provider_frame_count = 49
provider_trim_frames = 1

conditioning_frame_global_index = 96
conditioning_frame_is_emitted = true
preceding_boundary_global_frame_index = 95
preceding_boundary_frame_reemitted = false
```

Candidate C identity/reference policy remains:

```text
direct_provider_reference_ids = []
reference_conditioning_mode = baked_into_governed_keyframe
combined_identity_video_reference = false
```

This preserves the accepted keyframe-first architecture and avoids the earlier
multi-person combined-reference failure mode.

## Span-output verification and assembly

The operator provides the normalized provider outputs in governed span order.

VSCS uses `ffprobe` to verify each output before assembly.

Each span must have:

- the exact governed frame count;
- the governed frame rate;
- dimensions consistent with every other span.

For the Ros case:

```text
SPAN-001 must contain exactly 96 frames
SPAN-002 must contain exactly 48 frames
```

A raw 97-frame or 49-frame provider output is rejected until the accepted Candidate C
normalizer has reduced it to the governed frame count.

The normalized videos are concatenated with FFmpeg stream copy and provider audio is not
carried into this visual assembly.

The final result must have exactly the governed Shot frame count.

For SHT-002:

```text
final_frame_count = 144
```

The assembly record checksum-pins:

- each normalized span source file;
- each span's exact frame count;
- the final assembled file;
- final dimensions;
- final frame rate;
- final SHA-256 checksum;
- source internal-span plan ID and fingerprint.

If a source span or the assembled Shot later changes, existing assembly evidence is no
longer current.

## Human visual QC

A human reviewer must explicitly confirm every introduction boundary.

The four required observations are:

1. introduced asset is absent before the governed boundary;
2. introduced asset is present from the target frame;
3. visual continuity from the source span is preserved;
4. no unapproved asset appears at the transition.

All four observations must be true for the boundary QC record to pass.

For the Ros case, human acceptance therefore explicitly records:

```text
Ros absent through global frame 95
Ros present from global frame 96
continuity preserved across 95 -> 96
no unapproved people/assets introduced
```

A failed observation is persisted as QC evidence but does not transition the Shot to
`ACCEPTED`.

## Functional acceptance state

A dynamic Shot reaches `ACCEPTED` only when all of the following are current:

1. all required Governed Introduction Keyframes are approved;
2. normalized span outputs have exact governed timing;
3. internal boundary evidence matches the actual preceding span frame;
4. final assembled Shot has the exact governed total frame count;
5. source span files and final assembled output still match their stored checksums;
6. every introduction boundary has passing human visual QC.

Any stale or missing evidence moves the operator-visible status back to the appropriate
required state rather than silently preserving acceptance.

## Retry and execution governance

Phase 20.18.2.3.5 deliberately does not manufacture multiple ordinary provider attempts
for one ProductionTask.

The acceptance package builder:

- creates no ProductionQueue lease;
- creates no DurableExecutionJob;
- changes no retry count;
- grants no retry override;
- resets no execution history.

Dynamic Shots remain blocked from normal monolithic Start Production.

This is deliberate. A future production-orchestration phase may introduce a dedicated
sub-execution model for internal spans, but that model must preserve outer ProductionTask
attempt authority rather than treating each hidden span as an independent production
retry.

## Predecessor ProductionTask completion reconciliation

Cross-Shot continuity dependencies consume authoritative ProductionTask lifecycle state.
A predecessor Shot that already has technically valid, human-approved and authoritatively
selected Generated Media may therefore still need its task reconciled from `READY` to
`COMPLETED` before a dependent dynamic Shot can become READY.

The Production Tasks UI now exposes **Reconcile Task Completion** for a selected
`READY`, `RUNNING`, or already-`COMPLETED` task.

This control delegates to the existing Phase 20.13
`ProductionTaskCompletionReconciliationService`. It does not mark a task complete
manually and does not trust provider success alone.

Completion requires:

- authoritative selected Generated Media for every expected output kind;
- current APPROVED media state;
- passed technical validation;
- explicit human approval;
- explicit human selection;
- matching Generated Media revision;
- matching ProductionTask authority fingerprint.

For a `READY` task with valid evidence, the existing governed lifecycle is preserved:

```text
READY -> RUNNING -> COMPLETED
```

If any evidence is missing or stale, no task mutation occurs and the blocking findings
are shown to the operator.

This is particularly relevant to the accepted SHT-001 -> SHT-002 continuity chain:
SHT-002 remains PLANNED while its SHT-001 predecessor task is incomplete, and becomes
eligible for READY only after SHT-001 completion is reconciled from governed media
evidence.

## Functional acceptance procedure

For SHT-002:

1. Compile the current Production Package.
2. Confirm the UI reports two internal spans and one Introduction Keyframe requirement.
3. Approve the frame-96 Governed Introduction Keyframe and its frame-95 source evidence.
4. Build the two Candidate C span acceptance packages.
5. Execute those packages through the approved Candidate C LTX-2.5 workflow during
   functional acceptance.
6. Confirm provider outputs are normalized to 96 and 48 frames.
7. Select those normalized outputs in governed sequence and run
   **Verify & Assemble Span Outputs**.
8. Confirm the assembled Shot is exactly 144 frames at 24 fps.
9. Review the frame-95 -> frame-96 transition.
10. Record visual QC with all required observations.
11. Confirm Timed Span Acceptance becomes `ACCEPTED`.

## Deliberate exclusions

Phase 20.18.2.3.5 does not implement:

- autonomous visual recognition of Ros;
- automatic approval of visual QC;
- automatic production retry reset or extension;
- automatic multi-span ProductionQueue sub-jobs;
- hidden creation of multiple ProductionTasks for one editorial Shot;
- bypass of Generated Media governance;
- automatic promotion of a functional-acceptance assembly to approved production media.

Those require separate explicit governance decisions.
