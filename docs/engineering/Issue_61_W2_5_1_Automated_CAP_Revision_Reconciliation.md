# Issue #61 W2.5.1 — Automated CAP Revision Reconciliation

## Scope

The existing **Prepare from Reviewed CAP (Offline)…** action becomes
revision-aware. If a saved W2.5 human design revision is pending, it shows an
independent before/after review of the proposed replacements instead of using
the ordinary additive knowledge merge.

- Revision source: persisted, verified CAP review and revision history.
- Exact, previously reviewed field-bound facts and constraints are replaced.
- Generated Visual Identity / Production Notes lines are updated in place.
- Other facts, capabilities, classifications, metadata and freeform guidance
  are retained verbatim.
- Conflicting custom facts, custom constraints, ambiguous prose, stale revision
  fingerprints and unverifiable audits fail closed for independent review.
- Acceptance stages changes in the open editor only. **Save** persists them;
  Cancel discards them. No provider, GPU or image lifecycle operation is invoked.
- The completed revision fingerprint, operator acceptance and revision-history
  count are recorded with the CAP after Save. Subsequent revisions reconcile only
  new, previously unreconciled history entries.

## Windows acceptance — Maintenance Workstation

1. In **Canonical Profiles**, select `CAP-PRP-001` and click **Edit Selected**.
2. Confirm the Components row in **Reviewed CAP Specification & Decisions**
   reads **Edit**, with square corners and raised side returns; the CAP is Draft.
3. Scroll down to **Structured Production Knowledge** and click
   **Prepare from Reviewed CAP (Offline)…**.
4. In **Reconcile Reviewed CAP Revision — Human Acceptance**, inspect all
   before/after rows. Verify the obsolete chamfer requirements are replaced,
   and that the unchanged materials and scale are not being rewritten.
5. Click **Accept Reconciled Entries**. Inspect the updated Facts, Constraints,
   Visual Identity and Production Notes in the main CAP editor.
6. Click the main **Save**. Reopen the Production Contract and verify the values
   persist and the previous revision-refresh warning is cleared.
7. Confirm the original AI proposal and earlier review record remain available,
   CAP stays Draft, and the existing image remains Candidate.
8. Run **Review Visual Candidate…** to obtain a new advisory assessment against
   the current specification. Human MASTER and CAP approvals remain separate.

Cancel the reconciliation preview and close the CAP editor without saving for
the non-mutation test. The status/knowledge should be unchanged on reopening.
