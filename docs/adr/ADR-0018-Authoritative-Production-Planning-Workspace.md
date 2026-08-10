# ADR-0018 — Authoritative Production Planning Workspace

## Status

Accepted

## Context

By Phase 19.3.2 the Story Workspace exposed two overlapping planning systems at the same time:

- the new governed `Episode Planner → Scene Planner` hierarchy introduced by Phase 19.3; and
- the earlier Story Browser authoring path with `New Scene`, `Edit Scene`, `Delete Scene`, `Generate SSIE Plan`, `Shot Planner`, and `ACPP Editor`.

Both paths could appear to own Scene and Shot planning. Keeping both visible would make the production source of truth ambiguous, increase continuity risk, and undermine automation because downstream systems could not know which planning record was authoritative.

VSCS requires one authoritative planning environment. Other workspaces may display or navigate production objects, but they must not independently author the same planning level.

A corrective acceptance finding also showed that requiring an Episode to be `Ready` before any Scene Plan could be created made Episode/Scene planning unnecessarily sequential. Episode structure and Scene structure are naturally iterative. `Ready` must therefore represent a downstream authority boundary, not a prerequisite for drafting the next planning level.

## Decision

VSCS adopts a single authoritative planning hierarchy:

`Story → Episode Planner → Scene Planner → Shot Planner → specialist planners → production compilation`.

The Story Workspace remains the Story-level governance workspace and production navigator. It may display governed planning records and open the corresponding authoritative planner, but it no longer creates, edits, deletes, or generates competing legacy Scene/Shot planning records.

The Story Workspace therefore:

- renames its planning entry point to `Production Planning…`;
- presents governed Episode Plans and Scene Plans in the lower Production Overview;
- provides one context-sensitive `Open in Planner` navigation action;
- hides the legacy `New Scene`, `Edit Scene`, `Delete Scene`, `Generate SSIE Plan`, direct legacy `Shot Planner`, and direct `ACPP Editor` actions;
- preserves existing legacy Story/SSIE/Shot/ACPP data in project storage but does not present it as authoritative Phase 19.3 planning;
- keeps all mutations inside the planner that owns that planning level.

Scene Planning follows an iterative governance rule:

- a Draft Episode may own Draft Scene Plans;
- Scene Plans may be created, edited, runtime-budgeted, and deleted while the Episode remains Draft;
- a Scene cannot be promoted to `Ready` until its parent Episode is itself `Ready` and the Scene fingerprint matches the current Episode contract;
- Shot Planning may consume only a `Ready` Scene beneath a `Ready`, current Episode;
- preserved legacy scenes are shown in Scene Planner as `Legacy / Inactive` reference rows and have no edit/governance actions until an explicit migration converts them into authoritative Scene Plans.

## Single-authoritative-editor rule

Each production-planning level has exactly one authoritative editor:

- Story — Story Workspace;
- Episode — Episode Planner;
- Scene — Scene Planner;
- Shot — Phase 19.3.3 Shot Planner;
- Asset resolution — Phase 19.3.4 Asset Resolver;
- Camera — Phase 19.3.5 Camera Planner;
- Lighting — Phase 19.3.6 Lighting Planner;
- Environment — Phase 19.3.7 Environment Planner.

Other surfaces may inspect or navigate these records but cannot create a second mutation path.

## Consequences

- Operators have one unambiguous planning route.
- Episode and Scene planning can proceed iteratively without prematurely declaring the Episode production-ready.
- `Ready` remains a meaningful automation boundary for downstream Shot Planning.
- Downstream automation can treat governed planning records as the source of truth.
- Continuity cannot drift between two competing Scene or Shot editors.
- Legacy scenes remain visible for migration/reference without becoming accidental authority.
- The Story Workspace remains useful as a production overview without becoming a second planning system.
- Phase 19.3.3 can introduce the new Shot Planner inside the governed hierarchy without competing with the legacy Shot Planner button.

## Alternatives considered

### Keep both planning systems and document which one is preferred

Rejected because UI ambiguity remains and automation still has two candidate sources of truth.

### Require Episode Ready before Scene drafting

Rejected after acceptance testing because it forces a false one-way workflow. Episode structure and Scene decomposition must be able to evolve together while both remain Draft.

### Delete legacy Story/SSIE/Shot data immediately

Rejected because consolidation is an authority/UI change, not a destructive migration. Existing project information must be preserved until an explicit migration strategy is implemented and accepted.

### Remove the Production Overview entirely

Rejected because a read-only hierarchical navigator is valuable for orientation, status review, and context-sensitive navigation.

## Future notes

An explicit legacy Scene → Scene Plan migration workflow should preserve useful story intent while requiring human review before the result becomes authoritative.

Phase 19.3.3 must add Shot planning beneath a `Ready` governed Scene Plan and then project those governed Shot Plans into the Story Workspace Production Overview. It must not re-enable the legacy direct Shot Planner authoring path.
