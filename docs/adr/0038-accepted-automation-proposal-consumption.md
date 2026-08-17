# ADR-0038 — Accepted Automation Proposal Consumption

## Decision

Human-accepted current automation proposals are the preferred seed for their existing governed Draft-authoring owners.

The integration is proposal-to-Draft only. It never marks governed authority Ready, never bypasses existing planner prerequisites, never creates canonical assets, and never authorizes provider execution.

## Consumption map

- Episode proposals → existing Phase 19.5 deterministic orchestration → governed Episode authority.
- Scene proposals → existing Phase 19.5 deterministic orchestration → governed Scene authority.
- Shot proposals → existing Phase 19.5 deterministic orchestration → governed Shot authority.
- Action/Performance proposals → Phase 19.4 Action & Performance Draft creation.
- Environment proposals → governed Environment Planner suggested Draft creation.
- Camera proposals → governed Camera Planner suggested Draft creation.
- Lighting proposals → governed Lighting Planner suggested Draft creation.
- Continuity proposals → Phase 19.4 Continuity Draft creation, merged with current package-derived asset/dependency state.

Story Interpretation remains semantic proposal context rather than a separate production authority. Canonical Asset proposals remain under the dedicated XPD/CAP resolution and Shot asset-binding governance; acceptance does not create or alter canon automatically.

## Current-revision protection

A governed planner consumes only a proposal that is:

1. human Accepted and therefore consumable;
2. targeted at the selected governed Shot;
3. from the same Story source revision recorded by the current automation compilation report.

Accepted proposals from older Story revisions are ignored.

## Fallback

When no accepted/current proposal exists, the established deterministic suggestion behaviour remains unchanged.

## Governance

Creating a Draft from accepted automation is a human-triggered authoring action. The resulting Draft remains Draft until the user explicitly reviews it and marks it Ready through the existing governed planner/compiler lifecycle.
