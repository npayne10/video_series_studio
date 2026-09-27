# Phase 20.18.2.3.6.1 — Identity-Gated Character Entrances

## Purpose

Phase 20.18.2.3.6.1 hardens automated timed-span orchestration for identity-critical
character `ENTER` events.

Phase 20.18.2.3.6 proved that VSCS can render the preceding internal span, extract the
exact governed boundary frame, synthesize an introduced character from canonical
references, render the target span, and assemble one editorial Shot. Live acceptance
showed that structural automation alone is insufficient when the introduced character's
identity must match an approved canonical reference.

The failure mode was:

1. Qwen synthesized a plausible entrant that did not reliably match the canonical
   character identity.
2. LTX-2.5 received only the synthesized first frame and motion text; it did not receive
   the canonical identity reference as a separate video-stage conditioning input.
3. LTX could therefore reinterpret the entrance and create another entrant.

Phase 3.6.1 inserts a human identity-authority gate before any downstream target-span
render may use the synthesized candidate.

## Governed workflow

For a character whose Timed Asset Presence introduction is `ENTER`:

1. Render or safely reuse the preceding governed span.
2. Extract its exact final governed frame.
3. Compile a checksum-pinned introduction synthesis request.
4. Qwen Image Edit receives:
   - image 1: exact preceding boundary frame;
   - image 2: exact governed canonical reference for the introduced character.
5. Qwen generates one identity-review candidate.
6. VSCS persists the request, output, checksums, provider/model provenance, canonical
   reference IDs, reference paths, and reference checksums.
7. Automation stops at `KEYFRAME_REQUIRED`.
8. Production Execution exposes:
   - **View Identity Candidate**;
   - **Approve Identity**;
   - **Reject & Regenerate**.
9. A human approval promotes that exact candidate to the governed Introduction Keyframe.
10. Older assembly and visual-QC authority is invalidated without deleting audit history.
11. VSCS resumes automated orchestration:
    - safely reuses unchanged preceding spans;
    - builds the target span from the approved human-governed Introduction Keyframe;
    - renders remaining spans;
    - assembles the editorial Shot;
    - returns to final assembled-shot visual QC.

A rejection never promotes the candidate. It records a human rejection, increments the
governed synthesis attempt seed, and regenerates a new candidate while reusing valid
preceding provider work.

## Authority rules

### Character ENTER gate

A requirement is identity-gated when all of the following hold:

- the requirement introduces a governed asset;
- the Timed Asset Presence starts at the requirement target frame;
- the asset kind is `character`;
- the introduction semantic is `enter`.

Other introduction semantics retain the existing Phase 3.6 structural automation path.

### Human approval requirement

For an identity-gated character entrance, an Introduction Keyframe is current only when:

- the latest synthesized candidate passed structural provider validation;
- the latest candidate has an explicit human identity-review decision of `approved`;
- the review checksum matches the exact candidate image;
- the governed Introduction Keyframe has `approval_mode=human`;
- the keyframe image checksum matches the approved candidate;
- the keyframe remains current against the same Introduction Keyframe requirement.

An older `automated_structural` keyframe cannot satisfy this gate.

### Candidate rejection

A rejected candidate is immutable audit evidence. VSCS does not overwrite it. A new
attempt uses a different governed seed and therefore a different synthesis request
identity.

### Stale candidate protection

Phase 3.6.1 synthesis requests include `identity_gate_version=3.6.1`. Requests produced
before this contract are not eligible for the new identity-review UI and cannot be
approved as Phase 3.6.1 identity authority.

## Acceptance invalidation

Human identity approval or rejection invalidates older:

- timed-span visual-QC authority for the requirement;
- assembled-shot authority for the Shot.

Invalidation is append-only and timestamped. Previous records remain available as audit
history but are no longer current acceptance evidence.

## Provider behavior

The LTX-2.5 Candidate C workflow remains a single-governed-keyframe I2V workflow.
Phase 3.6.1 does not falsely claim that LTX receives a separate canonical character
reference. Instead, it requires the first target-span frame to have human-approved
identity before LTX is permitted to animate it.

The target-span motion contract must animate the exact already-visible approved entrant
and must not create, replace, duplicate, or add another entrant.

## Retry semantics

Identity candidate generation is internal governed orchestration. It does not consume a
new ProductionTask retry attempt. Rejected identity candidates increment only the
identity-synthesis attempt seed.

## UI acceptance criteria

When a candidate is pending:

- `Timed Span Acceptance` is `KEYFRAME_REQUIRED`;
- `Run Automated Span Orchestration` is disabled;
- `View Identity Candidate` is enabled;
- `Approve Identity` is enabled;
- `Reject & Regenerate` is enabled;
- the generic manual Introduction Keyframe approval action is disabled for the normal
  identity-gated path;
- the UI shows introduced asset IDs, canonical reference IDs, reference paths, reference
  SHA256 values, candidate path, candidate SHA256, target frame, and attempt number.

After approval, VSCS automatically resumes target-span orchestration. After rejection,
VSCS automatically generates the next candidate.

## Final visual QC

Identity approval is not final Shot approval. After target-span rendering and assembly,
the operator must still verify the assembled Shot for:

- introduced character absent before the governed boundary;
- correct approved character present from the governed entrance;
- no duplicate or unapproved people;
- stable existing-character identities;
- physical entrance continuity;
- camera/environment continuity;
- exact governed final frame count.

Only then may Timed Span Acceptance become `ACCEPTED`.
