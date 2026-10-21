# Phase Q3.1.3 — Reference Selection & Conditioning Governance

**Status:** proposal-only selection policy implemented and tests committed. Not integrated into governed production compilation. No render submitted.

## Evidence

Q3.1 3-reference run: 800x448, 56 frames / 24fps, 124.49 sec, continuity improved. Q3.1.2 4-reference run: same output dimensions and frames, 137.46 sec, 14 cached nodes, continuity preserved in sampled review. Original 5-reference 0.35 MP: 147.526 sec, 16 cached nodes, unwanted reference image inserts. Comparisons do not isolate causation because prompts and cache states varied. The third person's identity as Ros remains unverified by human.

## Policy

`h3_reference_selection_governance.py` offers deterministic, fingerprinted, **non-executable** proposals. Each candidate declares reference ID, kind, whether it is required by governing authority, and an asserted overlap with the frame-zero guide. There is no visual recognition here: overlaps must be supplied and verified by an operator. Required inputs always remain retained; a required count exceeding capacity fails closed for explicit replanning. Optional overlapping assets are merely *proposed* for deferment. The tool never applies deferment to execution slots, modifies a package, changes approval state, stages assets or submits a provider job.

Avoid treating the 5-reference limit as an excuse to omit scene requirements. Production adapter already has source-authoritative reference capacity, prioritization and deferred-reference checks. This policy is isolated until a subsequent authority integration explicitly reconciles existing precedence and provenance rules.

## Tests and local validation

    python -m ruff check .
    python -m ruff format --check .
    python -m mypy src
    python -m pytest -q tests/test_h3_reference_selection_governance.py -v
    python -m pytest -q
    git diff --check

## Follow-on acceptance needed before production integration

1. Map genuine compiled reference roles, priorities, IDs and frame-zero guide semantic evidence from governed Span inputs into this proposal model without guessing identity.
2. Explicit operator approval and provenance for any deferment, plus recompile/authority-fingerprint reconciliation against governed package.
3. Compiler/adapter functional tests for no silent drops, capacity conflicts, original input order, consistent IDs and provider slot matching; negative tests for stale approval.
4. UI read-only proposal/review affordance and manual acceptance; ensure approved QC and SHT-003 untouched.
5. Only after that, decide whether resolution 0.50 MP experiments are warranted.

No original TSR2 project changes, media retries, Shot approval/QC changes, ProductionTask changes, Episode assembly, or Picture Lock.
