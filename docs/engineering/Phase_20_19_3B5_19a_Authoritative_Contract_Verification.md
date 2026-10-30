# B.5.19a — Original planning hash calculators and CAP evidence forwarding

Status: Implemented on development branch; local Windows quality gates and disposable-project operator acceptance pending.

## Reused original calculators (not new hash conventions)
- `src/vscs/application/story/scene_planning.py` — `ScenePlanningService._episode_contract_hash(EpisodePlan)`.
- `src/vscs/application/story/shot_planning.py` — `GovernedShotPlanningService._scene_contract_hash(ScenePlan)`.
- `src/vscs/application/story/asset_resolver.py` — `GovernedAssetResolutionService._shot_contract_hash(ShotPlan)`.

`ProductionPlanningContracts` uses the original `_from_dict` deserializers and these exact existing hash functions. The read-only verifier checks structural Story→Episode→Scene→Shot ownership, parent contracts, matching binding contracts, source rereads, Ready statuses, and rejects Draft bindings. Verified Shot prose is converted into existing `ShotSpatialSource` preserving narrative source field names and bound asset IDs.

## UI
`StoryCAPBatchDialog.review_one` now attempts original governed planning verification when `planning/episode_plans.json` is present. Verified Shot sources feed `StoryCAPSpecificationDialog` offline. If verification fails, the dialog receives no Shot sources; the summary indicates why and no relationship is inferred. Sources are reverified after specification dialog acceptance and again immediately before persisted Draft CAP creation.

Only operator-confirmed Draft changes are eligible. No migration, duplicate Scene/Shot records, paid AI, Canon approval or H3 execution.

## Expected audit result
The disposable Episode Audit project currently has four Draft asset bindings. They are not ready authority, so governed evidence forwarding correctly fails closed until existing asset governance advances these bindings. The project is not changed automatically.

## Validation
New tests exercise actual production contract functions on typed models and verify Ready provenance, mutated Episode rejection and Draft binding rejection. The complete Windows lint, formatting, mypy and regression gates require the operator to run them after pulling the branch.
