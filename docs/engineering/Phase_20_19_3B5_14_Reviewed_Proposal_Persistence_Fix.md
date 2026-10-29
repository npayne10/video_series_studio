# B.5.14 follow-up — Retain reviewed dependency and geometry edits

## Reported behavior
Previously, the Story CAP Draft form's Save button only advanced to the next dialog. If a user cancelled the downstream detail review or reopened the cached proposal, the entered cross-asset dependency and geometry were reset to the original AI proposal.

## Correction
- The button now reads **Save Review & Continue** to distinguish saving operator work from committing a Draft CAP record.
- After successful field validation, `StoryCAPBatchDialog` stores a revised `StoryBatchProposal` in the existing project-scoped persistent proposal cache, preserving category, Story/asset/provider fingerprints, evidence, design suggestions and quality issues.
- The next **Review Cached Proposal** reloads the reviewed specification including operator-entered `dependency_constraints`, `dependency_asset_ids`, and optional `geometry` without another OpenAI call.
- This is *review-work persistence*, not a CAP record, Story Canon, reference approval, image generation or H3 execution. The final CAP creation step still requires a separately reviewed detail decision and explicit confirmation.
- No project asset/CAP record is written by this review-work save; the existing proposal-cache JSON is updated.
- Paid Regenerate Using AI explicitly replaces the existing cached reviewed proposal, as warned by its confirmation.

## Acceptance
1. Pull and restart VSCS.
2. Open cached `CAP-LOC-001`; enter `CAP-PRP-001|contains|forward bulkhead|900|mount>base` in Cross-asset dependencies.
3. Click **Save Review & Continue**. Close the spatial report and Cancel the CAP Detail Decisions dialog.
4. Reopen **Review Cached Proposal**; confirm the relationship remains in the field. Restart VSCS and repeat to confirm disk persistence.
5. Do not create a CAP or request paid regeneration.

```powershell
python -m pytest -q tests/test_phase_20_19_3b5_14_reviewed_cache_persistence.py -v
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest -q
git diff --check
git status --short
```
