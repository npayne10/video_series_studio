# Phase 20.18.2.3.7.3 — Checkpoint 4B.5

## Automated Draft Revision Discovery & Selection

Following a successfully verified, append-only Draft publication, Episode
Assembly immediately enumerates persisted revisions, selects the exact newly
created (assembly ID, revision ID) pair, fills the inspection identifiers, and
loads the persisted media selections. Episode-level coverage is refreshed when
a governed Episode is selected. A revision is *never* inferred from in-memory
staging; repository reading remains the authority.

The Available Revisions selector also supports direct browsing. Discovery
displays validated persisted records in descending identifier order, preserving
the selected revision when possible, without requiring manual re-entry of
identifiers. Invalid persisted evidence continues to fail closed.

A compact staged media summary shows each Shot, staged Generated Media ID,
saved source frame range, and missing-range status. Staging remains in memory
until a successful governed publication. The summary is not approval evidence.

The status message for an empty staging context now distinguishes absence of
staged production identity from absence of an authoritative planning snapshot.
Existing published revision inspection is independent of staging. Shot approval,
ProductionTask state, and Episode completion remain unchanged.

## Local verification

Run Ruff check/format, mypy, and full pytest. Focused tests:
`tests/test_phase_20_18_2_3_7_3_checkpoint4b5_revision_automation.py`,
`tests/test_phase_20_18_2_3_7_3_checkpoint4_revision_selection.py`,
`tests/test_phase_20_18_2_3_7_3_episode_assembly_workspace.py`.

UI: after a newly published immutable Draft, the existing revision should
appear selected and its Shot evidence should be visible immediately, without
re-entering Assembly ID or Revision ID. Verify the staged media summary shows
source in/out frames before publication, and that SHT-003 remains unavailable
until human QC. Do not publish a duplicate REV-001 in TSR2: use an isolated
test fixture for publication acceptance.
