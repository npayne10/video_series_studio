# Phase 20.18.2.3.6.6b — Provider-Aware Duration & Protected-Prefix Replanning

## Objective

Remove the legacy coupling between governed cinematic Shot duration and the
RTX 4060 / LTX provider ceiling, while preserving completed production exactly.

The Shot Planner owns editorial/narrative Shot structure. Provider and GPU limits
belong below Shot authority in provider execution infrastructure.

## Architecture decision

The planning flow is now:

Story / Ready Scene authority
→ semantic Shot authority
→ produced temporal-prefix protection
→ future semantic suffix recovery
→ provider-neutral cinematic Shot decomposition
→ specialist planning
→ UPD / ProductionTask
→ provider selection
→ provider-specific direct-duration validation
→ provider execution / governed span orchestration.

The governed planning ceiling for this phase is **15 seconds**. This is a
cinematic planning policy, not a claim that every provider/GPU pair has been
live-validated for a 15-second direct render.

The previous 7-second RTX 4060 / LTX hardware capability remains preserved as
provider execution evidence. It no longer dictates Shot Planner structure.

## Protected-prefix replanning

Automatic Scene replanning must never regenerate produced Shots merely to compare
them against a new planning limit.

The replanner:

1. detects durable production evidence;
2. requires protected Shots to form a contiguous prefix;
3. preserves that prefix exactly;
4. sums its authoritative elapsed runtime;
5. trims recovered semantic authority at that exact temporal boundary;
6. regenerates only the future semantic suffix under the current cinematic
   planning policy.

If the protected prefix consumes only part of one semantic beat, only the residual
portion of that semantic beat is regenerated.

If governed dialogue from that partial semantic beat was already delivered by a
protected Shot, the residual authority must not repeat or imply that dialogue.

If hardware-derived lineage exists but its semantic source archive cannot be
recovered unambiguously, replanning fails closed.

## Provider-specific direct duration

MiniMax H3 direct execution remains provider-specific infrastructure.

For the current H3 profile:

- provider-native frame rule: `17k+5`;
- direct-generation envelope: 15 governed seconds;
- RTX 5060 Ti duration validation candidates: 8, 10, 12 and 15 seconds;
- 24 fps governed/provider frame targets:
  - 8 s: 192 / 192 frames;
  - 10 s: 240 / 243 frames;
  - 12 s: 288 / 294 frames;
  - 15 s: 360 / 362 frames.

An H3 provider span above the 15-second direct envelope fails closed and requires
provider-capacity subdivision before execution.

The duration envelope does **not** alter the existing H3 provider-policy profile
fingerprint, so previously accepted production remains traceable to the exact
provider policy used to create it.

## Live validation status

The RTX 5060 Ti has already proven local H3 execution, including the accepted
SHT-002 governed span workflow and prior H3 temporal tests. This phase does not
infer a 15-second local production capability merely from 16 GB VRAM.

Before declaring the longer H3 direct duration production-validated, run the
controlled duration candidates in order:

1. 8 seconds;
2. 10 seconds;
3. 12 seconds;
4. 15 seconds.

Stop at the first duration that is not repeatably stable or fails technical /
visual acceptance. The highest repeatably accepted duration becomes evidence for
the local H3 direct-generation capability.

## Acceptance criteria

Implementation acceptance requires:

- Shot Planner governed duration is provider-neutral and no longer reads the
  legacy provider hardware ceiling as its planning limit;
- the governed cinematic ceiling is 15 seconds;
- SHT-001 and SHT-002 can be preserved exactly while only future elapsed Scene
  time is regenerated;
- accepted produced overrides do not destroy semantic lineage recovery;
- consumed dialogue is not repeated in regenerated residual authority;
- noncontiguous production evidence fails closed;
- ambiguous/unrecoverable semantic lineage fails closed;
- H3 direct provider spans above 15 seconds fail closed;
- UI clearly distinguishes cinematic planning duration from observed local
  hardware/provider capability;
- Ruff, mypy, focused tests and full regression pass;
- live Xorix replan preview shows SHT-001 and SHT-002 as PRESERVED before any
  mutation.

Functional acceptance additionally requires the controlled RTX 5060 Ti H3
duration validation sequence and the normal SHT-003 provider-selectable
production adoption.

## Phase state

Implementation is not equivalent to acceptance.

Phase 20.18.2.3.6.6b remains **OPEN / PENDING VALIDATION** until automated
validation, UI preview acceptance and the required live duration evidence have
been completed.
