# Phase 20.18.2.1 — Provider Reference Capacity Resolution

## Status

**Corrective implementation for Phase 20.18.2 live-provider acceptance.**

## Purpose

Phase 20.18.2.1 resolves a production acceptance defect discovered while compiling the
SHT-002 LTX 2.3 Production Package. The governed suitability review correctly preserved
all six visual authorities, but every canonical candidate was suggested as `required`.
The LTX Ingredients / IC-LoRA production workflow can consume at most three direct visual
references, so package compilation correctly blocked rather than silently discarding
governed authority.

The correction preserves the project principle:

> Required governed references are never silently dropped to satisfy provider capacity.

## Root Cause

The suitability authoring service assigned `ReferencePriority.REQUIRED` to every
canonical candidate irrespective of Shot semantics. For SHT-002 that produced six
required visual references:

- dialogue speaker;
- supporting character;
- location;
- environment context;
- visible planet;
- vehicle/ship.

The LTX provider edge supports three direct visual reference slots. This made the
production package structurally safe but non-executable.

## Corrective Design

### Semantic priority suggestions

The production suitability review now suggests priority from governed Shot semantics:

- characters are `required`;
- the primary location/set is `required`;
- environment/planet/vehicle/ship context is `preferred` unless its semantic role marks
  it as required, critical, hero, foreground, interacting, held, or used.

These are suggestions, not silent authority changes. Existing explicit suitability
reviews retain their persisted priority values until the operator explicitly chooses
**Apply Suggested Priorities** and then saves/approves the review.

For the observed SHT-002 authority this yields:

| Governed asset | Semantic role | Suggested priority |
| --- | --- | --- |
| CAP-CHR-003 | Dialogue Speaker | required |
| CAP-CHR-001 | Supporting Character | required |
| CAP-LOC-008 | Location | required |
| CAP-ENV-004 | Environment Context | preferred |
| CAP-PLN-002 | Visible Planet | preferred |
| CAP-SHP-002 | Vehicle/Ship | preferred |

The full governed ReferencePlan continues to contain and validate all six authorities.

### Capacity-aware suitability UI

The guided suitability review now shows a **Priority** column, an explicit
**Apply Suggested Priorities** action, and an LTX capacity status.

For LTX targets:

- zero required direct visual references blocks approval;
- more than three required direct visual references blocks approval;
- one to three required direct visual references passes the capacity gate;
- preferred provider-ready references are counted as candidates for any remaining slots.

The operator can still save an over-capacity explicit review for diagnosis, but cannot
approve it as provider-executable authority.

### Deterministic provider slot policy

At the LTX provider edge:

1. every required direct visual reference is selected first;
2. more than three required direct visual references still blocks compilation;
3. any remaining direct slots are filled deterministically with provider-ready
   `preferred` references;
4. `optional` references are not used merely to fill capacity;
5. continuity references remain separate from direct visual Ingredients slots;
6. the complete provider binding list remains in the Production Package for provenance.

This resolves provider capacity without weakening or deleting governed visual authority.

## Acceptance Criteria

### Automated

- semantic priority suggestions are deterministic;
- required references always precede preferred references;
- provider-ready preferred references may fill unused LTX slots;
- non-provider-ready preferred references do not consume slots;
- more than three required references still blocks with an explicit diagnostic;
- continuity reference authority does not consume direct visual capacity;
- Ruff, formatting, MyPy, and the full regression suite pass.

### UI / Functional

For SHT-002:

1. open **Reference Suitability**;
2. confirm the persisted six-required review reports `required 6/3 — OVER CAPACITY`;
3. confirm approval is disabled while over capacity;
4. click **Apply Suggested Priorities**;
5. confirm characters + location are `required`;
6. confirm environment context + planet + ship are `preferred`;
7. confirm capacity reports `required 3/3 ... PASS`;
8. inspect, save, and approve the suitability plan;
9. recompile current READY UPD authority and the replacement ProductionTask;
10. reschedule the replacement task;
11. compile the Production Package;
12. confirm the former “at most three required governed references” blocker is gone.

Do not start the provider during this corrective acceptance. The live LTX/ComfyUI run
continues under Phase 20.18.2 after package and deployment preflight succeeds.
