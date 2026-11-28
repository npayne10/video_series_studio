# Issue #61 W2.5.2 — Governed Candidate Requalification

## Purpose

Allow an existing **unchanged local PNG** to be independently accepted for a
fresh quality evaluation after a human-authorized CAP design revision. No
provider work or automatic lifecycle promotion is performed.

## Operator acceptance test

1. In **Canonical Profiles**, select `CAP-PRP-001` and click **Edit Selected**.
2. Select **Maintenance workstation — local visual candidate** in the gallery.
3. Click **Requalify Existing Candidate (Offline)…** (next to the visual-quality
   review actions near the bottom of the Production Contract).
4. Check that the dialog lists the original image SHA-256, prior and current
   specification fingerprints, and the revised `components` field.
5. Enter `Neill Payne` as reviewer. In rationale, record that the unchanged image
   has been independently inspected and is suitable for re-evaluation against
   the square-corner / raised-side-return specification.
6. Click **Create Requalified Candidate** and confirm the separate authority
   question. This creates a *new* supplementary Candidate record and a distinct
   managed PNG path (identical SHA-256 bytes), plus an audit manifest linking it
   to the original reference and original generation prompt.
7. Select **Maintenance workstation — requalified visual candidate** in the
   gallery. Click **Review Visual Candidate…**. The obsolete-fingerprint warning
   should not appear; choose offline technical-only or the independently
   consented semantic evaluation as appropriate.
8. Confirm the original Candidate, its image and its earlier manifest remain
   unmodified. Neither Candidate becomes MASTER/Approved automatically.

## Negative and safety tests

- Cancel the first dialog: no file or database changes.
- Empty reviewer, short rationale or rejected confirmation: no new Candidate.
- Changed image bytes, missing source, stale CAP review or unrelated historical
  design lineage: fail closed without creating a Candidate.
- Candidate Quality verifies the requalification source ID, original prompt,
  original manifest, and unchanged source and new image hashes.
- The new image is *not claimed to have been generated* from the revised prompt.
  Its evaluation context is clearly marked as offline requalification, and the
  original generation prompt remains in the lineage metadata.

The action applies to original local Visual Candidates; corrective/regenerated
or already requalified Candidate records need their own separate governance.
