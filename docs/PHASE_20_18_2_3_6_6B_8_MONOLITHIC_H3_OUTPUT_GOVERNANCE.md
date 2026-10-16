# Phase 20.18.2.3.6.6b.8 — Monolithic H3 Output Governance

## Scope

A governed one-span MiniMax H3 production plan uses the selected H3 adapter, not
legacy LTX Start Production. SHT-003 has 240 approved frames at 24 fps; its
opening boundary inherits SHT-002. The provider-capacity authority selects five
required direct references, deferring two preferred references.

## Output protection

* Provider output is normalized to its governed span count.
* After final assembly, ffprobe counts actual decoded video frames and fails
  closed when different from the approved Shot frame count. Manifest persistence
  and adoption follow successful validation, never precede it.
* Monolithic H3 output is copied into VSCS-managed Media Output and registered
  under a stable `GM-H3-...` Generated Media identity with checksum, observed/
  governed frame-count evidence, production scope, H3 provider plan, package
  fingerprint and direct-orchestration provenance.
* An explicit `H3DIRECT-...` execution profile assignment makes this provenance
  usable by downstream media review and closing-boundary authority checks. It
  does not impersonate a durable queue execution or consume a queued attempt.
* Media starts in `GENERATED`; an operator must use normal Generated Media
  review and approval. No automatic approval or completed task transition occurs.
* Provider adoption is `generated_pending_visual_qc` until governed human review.
  A monolithic Shot has no internal introduction boundaries and does not use
  timed-span boundary QC as its media approval substitute.

## Duplicate and partial-failure protection

A durable exclusive H3 launch claim is created per task/profile before provider
submission and retained across process failures. New readiness becomes blocked
whenever the claim exists. A second submission raises without rendering. Existing
H3 media or adoption also blocks automatic repeat registration. Operators must
not delete launch claims or modify task/queue/attempt JSON to retry; investigation
and a governed recovery workflow are required. This phase does NOT implement a
new automatic retry path.

## UI acceptance after automated tests

1. Restart VSCS, open D:\\VSCS TSR2, select SHT-003, production profile.
2. Confirm COMPILED package and inherited SHT-002 opening boundary.
3. Confirm MiniMax H3 readiness READY, one span, zero internal introductions.
4. Confirm legacy Start Production is disabled for selected H3.
5. Confirm Run Automated Span Orchestration is enabled **but do not click**.
6. Do not start live generation until final operator authorization after
   static checks, all regression tests and UI screenshot review.

## Regression gates

Run `python -m ruff check . --fix`, `python -m ruff format .`, review
`git diff`, then `ruff check`, `ruff format --check`, `mypy src`,
the focused H3 output governance tests and full `pytest -q`.
Any Ruff change must be mirrored directly to GitHub before release.

## Limits

This change does not introduce queue-based H3 execution or claim global
ProductionTask completion. The new direct-orchestration provenance remains
separate from durable queue attempts. Review of approved media, task
reconciliation and later closing-boundary publication remain governed follow-up
operations, not implicit consequences of successful generation.
