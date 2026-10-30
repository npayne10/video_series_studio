# B.5.19a UI acceptance follow-up

Status: GitHub implementation committed; Windows verification pending.

## Operator findings
The disposable Episode Audit displayed one governed Shot and four Draft bindings. Negative-path acceptance was 8/8 checks, with two inaccurate UI strings identified:
1. Governed Planning Authority Located claimed the original hash verifier was not connected.
2. Shot Spatial Evidence claimed legacy `story/shots.json` was the only source and suggested missing Story–Scene ownership.

## Corrections
- Governed discovery now states that original planners' contract calculators are connected, while separately explaining that CAP evidence is checked on proposal review and Draft bindings remain unapproved.
- Shot review accepts a source-aware `shot_evidence_status`; when governed forwarding fails, it displays `planning/shot_plans.json` and the actual verification failure instead of the unrelated legacy association message.
- Legacy-only flow retains legacy wording when applicable.
- Qt tests cover Ready-bound planning data with original contract checks and Yes/No confirmation before Draft-only field mutation. A separate test checks governed no-evidence messaging, ensuring the legacy file name does not appear.
- No production audit fixture mutation, duplicate Scenes/Shots, paid OpenAI usage or Canon approval.

## Remaining acceptance
Run targeted Qt tests, Ruff, mypy, complete regression; then review operator UI messages on the disposable project. The positive Qt test is an isolated UI acceptance at the specification dialog boundary, not a complete end-to-end operator run of the full CAP Batch window.
