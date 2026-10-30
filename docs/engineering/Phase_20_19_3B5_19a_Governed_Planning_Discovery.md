# B.5.19a — Governed planning authority discovery

Status: **partial delivery; not accepted**. Windows quality gates pending. Hash verification and production CAP evidence forwarding remain blocked.

## Verified user-supplied source structure
- `planning/episode_plans.json` episodes: Story ID, Episode ID, Story scope, status.
- `planning/scene_plans.json` scenes: Episode ID, Scene ID, episode contract hash.
- `planning/shot_plans.json` shots: Scene ID, Shot ID, scene contract hash, required action, narrative purpose, production objective.
- `planning/asset_resolutions.json` bindings: Shot ID, asset ID, status, shot contract hash.
- The audit's Episode, Scene and Shot were reported ready; four bindings were reported draft.

## Implemented
- Read-only `discover_governed_shot_evidence` walks the existing `planning/` record hierarchy with exact Story, Episode, Scene, Shot and binding IDs.
- Discovery preserves separate narrative fields, binding statuses and each stored contract hash. It rejects missing/malformed hashes and contradicting binding hashes; it **does not** claim recomputation or validity.
- For projects with governed plans and no legacy `story/scenes.json`, the operator now sees a source-aware discovery message instead of being directed to invent duplicate Scenes.
- The earlier operator-assignment ledger still supports legacy-only projects; it is not applied to governed production plans.

## Strict outstanding boundary
Hash formats have been inspected, but the production planning contract-hash calculation implementation is not yet identified in the connected branch source. It would be unsafe to treat un-recomputed hashes as approved evidence. The new discovery API deliberately sets `hashes_verified=False` and does **not** feed Shot prose into CAP relationship proposals. Full B.5.19a requires wiring the existing contract-fingerprint calculator, checking readiness authority, and revalidating immediately before any operator-confirmed Draft mutation.

## Local checks
```powershell
cd D:\VSCS\video_series_studio
git fetch origin
git pull --ff-only origin phase-20.18.2.3.6.3-local-r2v-provider-evaluation
python -m pytest -q tests/test_phase_20_19_3b5_19a_governed_planning_evidence.py -v
python -m ruff check .
python -m ruff format --check --no-cache .
python -m mypy src
python -m pytest -q
git diff --check
git status --short
```
