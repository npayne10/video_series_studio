# Phase 20.19.3B — Structured CAP Specification & Persistence Integration

Date: 2026-10-26
Status: Initial backward-compatible foundation committed; local regression validation pending
Depends on: Phase 20.19.3A audit

## Delivered

- `CAPStructuredSpecification` (`application/caps/structured_specification.py`): versioned, strict Pydantic envelope for the authored asset specification, immutable visual attributes, permitted presentation variants, creation/negative prompts, continuity, dependency IDs, source-document SHA256, source provenance and content fingerprint.
- Category contracts for Character, Location, Ship, Vehicle, Prop, Technology, Environment, Planet and Uniform; other registered categories may persist general identity fields without imposing a wrong category template.
- Reject an empty design intent, empty prompt, missing/empty canonical attribute, invalid SHA256, attributes simultaneously locked and variable, and mismatched asset categories.
- `CAPStructuredSpecificationService.save_draft` links to the **existing** project-scoped `CAPService` and `AssetService`; requires the CAP already exists and is Draft. It merges the serialized specification into existing `production_metadata` using key `vscs.structured_cap_specification.v1`.
- `get` retrieves and validates the persisted spec, while a legacy CAP with no specification continues to function unmodified.
- No database schema change, new independent asset table, implicit status approval, reference promotion or provider image submission.
- Focused unit tests: category contract checks, fingerprint, source digest validation, metadata preservation, approved-CAP rejection, category mismatch, legacy read, and cross-asset record mismatch.

## Data ownership

The current `canonical_asset_profiles` table already has `production_metadata_json`, `facts_json`, `functional_identity_json`, `constraints_json` and additional structured fields. The first-phase envelope intentionally reuses `production_metadata_json` rather than duplicating CAP authority or requiring a migration. Existing CAP and canonical-reference status rules remain in force. The authored spec is a **Draft supplement**, not a production-approved source.

## Source document mapping

The provided Xorix Character CAP includes permanent appearance, design intent, variant controls, dependencies, continuity, and a master prompt. The Location CAP includes locked geometry, layout, architecture/materials, sightlines and space, plus variable camera/occupancy/time/weather/view and a master prompt. Those map into `canonical_attributes`, `allowed_variants`, `dependency_asset_ids`, `continuity_rules` and `master_prompt`. **This phase does not parse DOCX files**; importer and category-dependent field-by-field completeness validation require a separately approved implementation. An imported CAP ID is always resolved relative to the target project and cannot overwrite colliding assets.

## Explicit boundaries and follow-on work

1. Extend category schemas to all native asset categories, with field-level strictness and human-readable help.
2. Implement document ingestion with a preview-and-map stage; preserve original file hash, section provenance, revisions and document-only LOCKED claims.
3. Add operator UI entry points from Asset Manager and Story Intelligence for **Draft specification creation and review**.
4. Resolve immutable edited CAP revision policy with existing CAP reference fingerprints; do not mutate approved CAPs directly.
5. Implement read-only XCIC/ComfyUI environment readiness, separate image-generation approval and candidate QC in Phase 20.19.3C onward.
6. Consider transactional compare-and-swap on CAP status/metadata for competing editor saves before enabling multi-window operation. Current read/merge/write is not a concurrency proof.
7. Add SQLAlchemy persistence tests in local full suite before granting phase acceptance. Focused first-pass tests use fakes and do not prove database durability.

## Golden Path safety

`D:\VSCS\GOLDEN_PATH_AUDIT\RUN-001\Episode Audit` and `D:\VSCS\H3_ACCEPTANCE\Q3_1_3_5_8\RUN-001` are not modified by these commits. Four inferred Shot bindings remain Draft and are **not** ready. H3 live video generation remains on hold. No ComfyUI image generation or provider submission is performed.

## Local validation instructions

```powershell
cd D:\VSCS\video_series_studio
git fetch origin
git pull --ff-only origin phase-20.18.2.3.6.3-local-r2v-provider-evaluation
python -m pytest -q tests/test_phase_20_19_3b_structured_cap_specification.py -v
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest -q
git diff --check
git status --short
```

Expected: all pass, clean Git status. The focused tests should not open VSCS or send requests. Existing Assets and Canonical Profiles UI should remain unchanged. No Master approval and no Ready conversion may occur as a side effect.
