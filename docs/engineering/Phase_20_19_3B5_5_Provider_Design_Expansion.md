# Phase 20.19.3B.5.5 — Provider-backed canonical design expansion

Status: implementation committed, Windows automated tests and UI acceptance pending.

The OpenAI CAP adapter now makes a separate read-only structured response request for the missing category fields after the normal canon-only CAP draft. It asks for physically plausible production-design choices **as proposals**, not canon facts. The response is restricted to one nonempty value and rationale per valid missing field. Existing attributes cannot be overwritten by this response. An unsupported provider keeps the earlier no-suggestion behavior.

The Story CAP batch preview carries proposals in memory. The second field-level review dialog pre-fills the suggested value and explanatory rationale but defaults the decision to **Defer**. Only explicit Accept or Edit decisions enter Draft canonical_attributes when the operator completes the existing final save confirmation. Reject/Defer do not authorize or persist those values as fixed design. All accepted decisions are still classified as unapproved design proposals; provenance records and Draft-only guard from B.5.4 remain in force.

Cautions: This adds a **fourth** OpenAI CAP API stage and may incur cost. It does not validate design physics, Story source spans or canon evidence; no persistent revision ledger. The earlier batch save code re-previews the Story, and therefore may repeat model calls. That optimization and immutable provenance histories remain future work. No ComfyUI media provider, image, video, or H3 execution is triggered by this phase.

## Test
```powershell
cd D:\VSCS\video_series_studio
git fetch origin
git pull --ff-only origin phase-20.18.2.3.6.3-local-r2v-provider-evaluation
python -m pytest -q tests/test_phase_20_19_3b5_5_provider_design.py tests/test_phase_20_19_3b4_story_cap_specification.py -v
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest -q
git diff --check
git status --short
```

UI: disposable Episode Audit → Story → CAP Batch → Generate Proposal for CAP-LOC-001 → initial review Save (not persistence) → inspect suggested values and Defer defaults in field review → Cancel. Four registered missing CAP assets should remain missing. The permanent H3 live-generation hold remains unchanged.
