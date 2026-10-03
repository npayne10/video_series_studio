# Phase 20.18.2.3.6.4 — Provider-Enforced Temporal Reference Isolation

## Purpose

Phase 20.18.2.3.6.4 redesigns dynamic timed-asset execution so a provider cannot see a
canonical asset reference before the exact governed frame where that asset becomes active.

The redesign is driven directly by the MiniMax H3 d.2 failure.

The provider-neutral authority introduced in Phases 20.18.2.3.1 through 20.18.2.3.3 was
correct: Ros must be structurally unavailable before frame 96. The failed d.2 experiment
showed that a monolithic H3 Ref2VA render violates that rule because global references and
prompt conditioning remain available across the entire generated sequence.

The system must therefore enforce temporal isolation at the provider-job boundary rather
than trying to simulate it inside one monolithic provider render.

## Failure evidence driving the redesign

For SHT-002:

- governed Shot: 144 frames at 24 fps;
- Ros introduction boundary: global frame 96;
- d.2 H3 run: 175 generated frames;
- frame-0 guide produced the correct two-person opening state;
- Ros became visible by frame 1 even though his intended introduction was frame 96;
- the second H3 guide at frame 96 did not suppress Ros before that frame;
- immediately after the second guide, the generation destabilized into a full-frame Xorix
  shot and lost the bridge/characters.

Conclusion:

`MiniMaxH3AddGuide(frame_idx=N)` is not a hard temporal asset-activation gate.

A guide can anchor visual state, but it cannot revoke shot-global access to an identity
reference already supplied to Ref2VA.

## Core architectural rule

For every dynamic Shot:

> A provider job may receive only the canonical references and asset-specific prompt
> content authorized for that exact governed internal render span.

Future-span references must not exist in:

- provider reference slots;
- prompt text;
- guide images;
- auxiliary conditioning inputs;
- provider-specific metadata;
- cached provider jobs reused for the earlier span.

Temporal authority is enforced by job isolation, not by prose.

## SHT-002 execution topology

The editorial Shot remains one Shot:

```text
EP-001-SCN-001-SHT-002
24 fps
144 governed frames

SPAN-001
global 0-95
96 governed frames

SPAN-002
global 96-143
48 governed frames
```

### SPAN-001 provider authority

Allowed active identities:

- James;
- Sandra;
- Iron Horizon bridge/environment;
- Xorix/environmental planetary authority where required.

Explicitly forbidden:

- Ros canonical identity reference;
- Ros name in provider prompt;
- Ros entrance instruction;
- any Ros-bearing image or guide;
- any future-span reference containing Ros.

Opening conditioning:

- accepted Shot opening/boundary frame at local frame 0;
- provider-specific frame-0 guide if the provider supports it.

The provider therefore has no way to introduce Ros from canonical conditioning.

### SPAN-002 provider authority

Allowed active identities:

- James;
- Sandra;
- Ros;
- Iron Horizon bridge/environment;
- Xorix/environmental planetary authority where required.

Opening conditioning:

- approved frame-96 Introduction Keyframe;
- mapped to SPAN-002 local frame 0;
- checksum-pinned and required to represent the first emitted frame of the target span.

Ros canonical identity reference becomes legal only in this provider job.

The prompt may describe Ros's continued physical entrance because the asset is already
active at the span opening.

## H3-specific provider policy

For MiniMax H3 Ref2VA:

1. Never run a dynamic multi-span Shot as one monolithic H3 job.
2. Never use a later `MiniMaxH3AddGuide` as an asset-activation gate.
3. Use at most the local span-opening guide as temporal frame-state authority.
4. Compile H3 references independently for every span from
   `TimedCanonicalReferenceActivationPlan.active_reference_ids`.
5. Compile H3 prompt content independently for every span from active assets only.
6. The opening guide is not counted as a canonical identity reference.
7. Ros's canonical reference is absent from SPAN-001 and available only in SPAN-002.
8. Normalize each H3 output to the exact governed span frame count before assembly.
9. Concatenate normalized spans in governed sequence.
10. Final visual QC evaluates the assembled editorial Shot.

## Provider-neutral execution contract

Introduce a generic provider execution contract:

`ProviderTemporalSpanExecution`

Each record contains:

- Shot ID;
- governed span ID;
- sequence number;
- global start and through frame;
- governed frame count;
- provider-request frame count;
- active asset IDs;
- active reference IDs;
- introduced reference IDs;
- removed reference IDs;
- opening frame-state authority kind;
- opening image path;
- opening image SHA-256;
- provider prompt fingerprint;
- provider workflow fingerprint;
- provider ID;
- provider mode;
- normalization policy;
- assembly sequence.

The contract must be derived only from already-governed authority:

- Timed Asset Presence;
- Internal Render Spans;
- Timed Canonical Reference Activation;
- Introduction Keyframe requirements/approvals;
- provider capability profile.

No provider adapter may add an asset not present in the contract.

## Prompt compilation redesign

Prompt compilation becomes span-scoped.

The compiler receives:

- active assets for the span;
- active canonical references;
- introduced assets at local frame 0;
- removed assets at local frame 0;
- stable environment/frame-state authority;
- provider capability profile.

The compiler must omit all future assets.

For SPAN-001, the H3 prompt must not contain the tokens:

- Ros;
- Rohsgard;
- CAP-CHR-005;
- Picture tag associated with Ros;
- any instruction saying that Ros enters later.

This is intentional. Saying "Ros enters later" still exposes Ros semantically to a
shot-global generative model.

For SPAN-002, Ros may be declared normally because his authority begins at local frame 0.

## Reference-slot compilation redesign

Reference slot assignment must be deterministic per span.

Example H3 SPAN-001:

```text
Picture 1 = James
Picture 2 = Sandra
Picture 3 = bridge
Picture 4 = Xorix
```

There is no reserved or empty Ros slot.

Example H3 SPAN-002:

```text
Picture 1 = James
Picture 2 = Sandra
Picture 3 = Ros
Picture 4 = bridge
Picture 5 = Xorix
```

Prompt picture tags are compiled from the actual per-span slot map. They must not reuse a
shot-wide static index mapping.

## Opening-guide policy

The failed d.2 experiment changes guide semantics in VSCS.

A provider guide is classified as:

`FRAME_STATE_ANCHOR`

It is not classified as:

`TEMPORAL_ASSET_GATE`

For H3:

- SPAN-001 guide local frame index = 0;
- SPAN-002 guide local frame index = 0;
- no frame-96 guide exists inside either isolated job;
- the global frame-96 meaning comes from SPAN-002's governed global start frame.

This removes the ambiguous provider behavior observed at frame 97 in d.2.

## Frame-count normalization

Providers may have native frame-grid restrictions.

The provider adapter may request more frames than the governed span only when required by
the provider.

The normalization contract is:

```text
provider output
    -> decode
    -> retain exact governed emitted-frame interval
    -> discard provider-only surplus frames
    -> persist normalized span
```

For SHT-002:

- normalized SPAN-001 must contain exactly 96 frames;
- normalized SPAN-002 must contain exactly 48 frames;
- final assembly must contain exactly 144 frames.

No provider-generated surplus frame may cross a governed span boundary.

## Assembly policy

Assembly remains provider-neutral:

```text
normalized SPAN-001
+
normalized SPAN-002
=
one editorial SHT-002
```

The assembly runtime must prove:

- correct span order;
- exact frame counts;
- no duplicated preceding-boundary frame;
- frame 95 is the final frame of SPAN-001;
- frame 96 is the first frame of SPAN-002;
- final frame count is exactly 144.

## Temporal leakage gate

Before provider submission, validate:

`active_reference_ids == provider_reference_ids`

and:

`future_reference_ids ∩ provider_reference_ids == ∅`

Prompt validation must also reject known inactive canonical asset identifiers/names when
they are emitted by structured prompt compilation.

For SHT-002 SPAN-001, the provider submission fails closed if any Ros reference or
structured Ros prompt content is present.

## Cache and retry isolation

Provider cache keys must include:

- span ID;
- activation-plan fingerprint;
- opening-guide SHA;
- provider reference-slot fingerprint;
- provider prompt fingerprint;
- workflow fingerprint;
- model/config fingerprint.

A cached SPAN-001 render created with Ros present in its reference set is never reusable
after this redesign.

Retries remain editorial-Shot governed, but individual span outputs may be reused only
when every authority fingerprint still matches.

## Persistence hardening

The d.2 recovery also exposed an unrelated but important defect: approved visual authority
could be overwritten at a mutable path.

Any approved boundary/keyframe used by span execution must be preserved by content identity.

Required policy:

- approved media receives an immutable checksum-specific path;
- governed metadata points to that immutable file;
- mutable candidate paths may never replace approved bytes;
- checksum mismatch fails before provider submission.

## UI behavior

For a dynamic Shot, Production Execution should expose one editorial action:

`Run Governed Dynamic Shot`

The operator should not need to manually manage provider spans in normal production.

The UI may display progress:

```text
SPAN-001  frames 0-95    Rendering
Boundary  frame 96      Preparing
SPAN-002  frames 96-143 Waiting
Assembly               Waiting
Visual QC              Waiting
```

Manual span controls remain recovery-only.

## Implementation slices

### 20.18.2.3.6.4a — Generic Temporal Span Execution Contract

Implement provider-neutral span execution records and validation.

Acceptance:

- contract reconstructs exact SHT-002 span topology;
- Ros absent from SPAN-001 references;
- Ros active in SPAN-002;
- stale fingerprints fail closed.

### 20.18.2.3.6.4b — Span-Scoped Prompt and Reference Compilation

Implement deterministic provider-facing per-span reference-slot maps and prompts.

Acceptance:

- SPAN-001 contains no Ros reference and no Ros structured prompt content;
- SPAN-002 contains Ros and maps tags consistently;
- environment references remain stable.

### 20.18.2.3.6.4c — MiniMax H3 Span Adapter

Implement H3-specific execution planning:

- local frame-0 guide only;
- per-span Ref2VA reference set;
- per-span prompt;
- provider-native frame count;
- normalization to governed frame count.

Acceptance:

- no later in-job guide used as an asset gate;
- H3 SPAN-001 job has no Ros conditioning;
- H3 SPAN-002 starts from approved introduction frame.

### 20.18.2.3.6.4d — Governed Span Orchestration and Assembly

Integrate H3 into existing automated span orchestration without changing editorial retry
authority.

Acceptance:

- two H3 jobs execute in sequence for SHT-002;
- normalized outputs are 96 + 48 frames;
- final assembly is exactly 144 frames;
- frame 95 -> 96 boundary is preserved.

### 20.18.2.3.6.4e — Functional Acceptance

Run the real SHT-002 case.

PASS requires:

- frames 0-95: James + Sandra, Ros absent;
- frame 96: first visible Ros entrance state;
- frames 96-143: Ros may continue entering;
- no extra people;
- James/Sandra continuity maintained;
- central chair continuity maintained;
- bridge/Xorix coherent;
- no cut caused by provider guide semantics;
- final Shot exactly 144 frames at 24 fps.

## Explicitly rejected approaches

The following are no longer valid for timed asset activation:

- one monolithic H3 render with all future references supplied globally;
- prompt-only phrases such as "Ros enters later";
- repeated negative prose intended to suppress a future asset;
- a second in-job H3 guide at global frame 96;
- relying on provider interpretation of exact frame numbers.

## Architectural decision

Timed asset activation is a VSCS orchestration responsibility.

Providers generate only within the authority they are given.

For providers with shot-global conditioning, VSCS must physically isolate temporal spans.
For a future provider that proves native hard timed-reference activation, the provider
capability profile may permit a single job, but only after capability-specific acceptance
tests prove that inactive references are inaccessible before their governed frames.
