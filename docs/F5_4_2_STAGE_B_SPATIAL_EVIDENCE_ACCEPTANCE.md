# F5.4.2 Stage B — Structured Visual Evidence and Spatial Correction Proposals

**Status:** GitHub implementation candidate. Local Windows Ruff, Mypy, full regression,
CAP non-mutation audit and operator UI acceptance **not yet verified**. Do not mark
Stage B accepted until those gates are completed.

## Scope and decision

Stage A's Candidate quality review and typed defect triage remain unchanged.
Stage B introduces an in-memory, immutable, review-only evidence projection over
the **accepted** Draft CAP fields from the saved quality-result snapshot.

- Every reviewed field starts `UNKNOWN`, even when the semantic evaluator provides
  a positive overall result. Advisory evaluator violations never create CAP design
  authority or independently mark a requirement failed or passed.
- A human may label one selected reviewed field `FAILED`, with a typed defect and
  12–2000 characters of observed evidence, optionally supplying a normalized
  proposed rectangle `x,y,width,height` within the source image.
- A human may label a reviewed field `VERIFIED_BY_OPERATOR`, with at least
  12 characters of observation. This is a transient, non-authoritative reviewer
  assertion — not semantic auto-pass, Canon approval, or CAP promotion.
- All unselected fields remain `UNKNOWN`. There is no aggregation of decisions
  across clicks or persisted review journal at this stage.
- The source-image SHA-256 from the saved review is echoed in the proposal.
  The caller supplies the expected image SHA to reject stale/mismatched evidence.
- A proposed ROI is **not a verified mask** and does not permit pixel editing.
  Region approval remains false; no masks are generated or persisted.
- The existing F5.4.1D defect→stage mapping is reused for a failed field.
- GPU submission, attempt reservation, CAP registration and Canon approval remain
  false. No filesystem mutation or network call is performed by this service.

## Operator UI

1. Open an existing semantically evaluated Candidate quality report.
2. Choose **F5.4.2 Review General Visual Correction (No Generation)…**.
3. Select one accepted Draft CAP field, a defect, and enter observed visual evidence.
4. Under **Stage B**, choose `FAILED` (or `VERIFIED_BY_OPERATOR` with evidence).
5. For a failure, optionally enter source-relative `x,y,width,height` values, each
   normalized to 0..1, with strictly positive width/height and no overflow.
6. Press **Inspect Stage B Evidence / ROI (No Generation)**.
7. Inspect the returned per-field states and optional ROI. Confirm no generation,
   mask, authority change, attempt use or CAP write. Closing loses this advisory
   inspection; nothing is saved.

## Gates before approval

Run on Windows after fetching the Stage B branch:

```powershell
cd D:\VSCS\video_series_studio
git status --short
git fetch origin
git switch phase-f5.4.2-stage-b-visual-evidence-roi
git pull --ff-only origin phase-f5.4.2-stage-b-visual-evidence-roi

python -m ruff check .
python -m ruff format --check --no-cache .
python -m mypy src
python -m pytest -q tests/test_cap_general_visual_correction_triage.py tests/test_cap_spatial_visual_evidence.py tests/test_cap_visual_candidate_quality.py tests/test_cap_geometry_correction_policy.py tests/test_cap_visual_candidate_regeneration.py
python -m pytest -q
git diff --check
git status --short
```

Operator UI tests: verify UNKNOWN is not a pass, FAILED requires evidence plus
defect, VERIFIED_BY_OPERATOR requires evidence without defect/ROI, invalid or
out-of-bounds ROI is blocked, a source SHA mismatch fails closed, and review
does not mutate stored Candidate, reports, attempts or CAP authority.

**Stop rule:** Do not enable generation, import ROI as an approved mask, or unlock
Candidate 4's protected final Attempt 2/2. The previous isolated dial experiment
is closed. Later Stage C requires a separately approved contract.
