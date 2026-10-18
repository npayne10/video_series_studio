# Phase 20.18.2.3.7.3 — Checkpoint 4B.4.1

## Governed initial partial Draft scope

An Episode planning snapshot is an append-only, explicitly operator-authorized
record of **the currently persisted READY Episode and Scene Plans**, their full
ordered Shot Plans, and the sole persisted production identity of staged media.
It is not a Shot QC approval, Generated Media approval, Shot-set completion
declaration, or Picture Lock.

The snapshot captures full planning contents and their SHA-256 fingerprint,
an independently identifiable revision, required Shot order, and operator identity.
On every use the resolver reloads and integrity-checks the snapshot and
recalculates current planning structure; changed plans or production ownership
fail closed. Publishing a snapshot is an explicit QMessageBox-confirmed operator
action. The existing completed Shot-set declaration route is retained as a
separate scope authority.

The Draft editor only stages approved media. Building a partial Draft permits
blockers on **other unfinished Shots** but rejects blockers on a **selected
Shot**. The final Draft publisher continues to require explicit frame ranges,
recorded approval-event references, actual Generated Media verification and the
append-only timeline repository.

The Episode Complete button remains disabled. Initial partial Draft publication
does not enable full-episode assembly, final-use assembly, Picture Lock or
mastering.

## Acceptance

Run Ruff lint/format, mypy, focused snapshot and partial Draft tests, UI tests,
the complete regression suite, then inspect the Episode Assembly page. The
planning snapshot button requires a staged-media production identity, an operator,
a resolved Episode with Ready Scene plans and affirmative operator confirmation.
Only afterwards may the immutable partial Draft publication button become
enabled, subject to all its original guards. Reject/stale-scope cases must leave
the button disabled, without touching production evidence.
