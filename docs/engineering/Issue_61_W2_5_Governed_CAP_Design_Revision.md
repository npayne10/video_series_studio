# Issue #61 W2.5 — Governed CAP Design Revision

## Purpose

The Production Contract displays the persisted human-reviewed CAP specification. An
operator can now revise a **saved, accepted or edited field** of a **Draft** CAP without
discarding the original design-review audit or changing image/CAP approval.

## Operator workflow (CAP-PRP-001)

1. Open **Canonical Profiles**, select `CAP-PRP-001 — Maintenance workstation`,
   then **Edit Selected**.
2. Scroll to **Reviewed CAP Specification & Decisions** and select `components`
   in the table.
3. Click **Revise Reviewed Specification…**. The original value is read-only.
4. Replace the revised specification with the agreed square-corner, raised-side-
   return description; retain the four legs, rear lip, lower shelf and separation
   from the diagnostic console.
5. Enter the reviewer name and reason, then click **Save** and confirm
   **Authorize Design Revision?**. This is an explicit human decision.
6. Close the Production Contract and reopen it to inspect the effective value,
   `Edit` decision, revision rationale, and refresh warning. **No image generation
   or approval is triggered.**
7. Use **Prepare from Reviewed CAP (Offline)…** to prepare revised knowledge and
   guidance; check and reconcile old statements describing chamfered corners.
   Existing unrelated facts, classifications and metadata must be preserved.
8. Reassess the visual candidate against the new specification. MASTER registration,
   independent visual acceptance and CAP approval remain separate governed actions.

## Governance and persistence

- Only Draft CAPs with a verifiable existing field-level design-review audit qualify.
- A stale specification fingerprint, unchanged value, missing reviewer/rationale or
  deferred/rejected field blocks the mutation before persistence.
- The revised effective specification and field-level audit are stored together in
  existing CAP production metadata, with the previous entire specification and
  audit appended to `vscs.cap_design_revision_history.v1`.
- `vscs.cap_design_revision_refresh.v1` records the downstream reconciliation
  requirements for structured knowledge, identity/guidance and image reassessment.
- The generic editor preserves both revision keys and reloads current governed
  metadata at Save, preventing a stale dialog snapshot from undoing the revision.
- A design revision does not change CAP status, image lifecycle, MASTER authority,
  human QC records or provider execution state.

## Limitations

The W2.5 button revises *existing accepted/edited fields*. Promoting a previously
deferred field requires the separate full design-review workflow. Downstream refresh
is explicitly flagged for operator review; it is **not silently applied** and the
refresh warning is retained for audit until a later governed reconciliation feature
can establish that all dependent artifacts are current.
