# ADR-0035 — Automated-Validated Introduction Boundary Governance

## Status

Accepted for Phase 20.18.2.3.6 implementation; live acceptance remains pending.

## Context

Phase 20.18.2.3.5 required a human to provide both the preceding internal-boundary image and the target Introduction Keyframe for every in-Shot timed asset introduction. This proves governance but creates production work proportional to the number of introductions and therefore conflicts with VSCS automation goals.

VSCS already holds the information needed to automate routine introductions: exact Timed Asset Presence, deterministic internal spans, canonical reference activation, the Introduction Keyframe requirement, normalized span outputs, and governed reference imagery.

## Decision

VSCS will treat routine Introduction Keyframe creation as an automated governed production operation when automated validation can establish the required acceptance criteria.

GovernedIntroductionKeyframe supports two approval modes:

- human: explicit human approval, retaining the Phase 3.4/3.5 behavior.
- automated_validated: system-created authority backed by persisted synthesis and validation provenance.

Automated authority is not represented as human approval. It records the automation actor and an immutable project-relative provenance record.

The normal dynamic-Shot execution path becomes sequential:

1. execute preceding governed span;
2. extract its exact normalized final frame;
3. synthesize the next target frame using governed introduced canonical references and continuity constraints;
4. validate the synthesized frame automatically;
5. register a checksum-pinned automated-validated Introduction Keyframe;
6. execute the next span;
7. assemble exact normalized spans;
8. validate the rendered boundary again;
9. use manual review only if automation cannot pass.

Provider capability is selected through a provider-neutral ladder: provider-native timed reference injection when genuinely supported, otherwise synthesized target-keyframe conditioning when image editing plus first-frame I2V is available, otherwise manual fallback.

## Consequences

Routine asset introductions no longer require manually created boundary images. Existing human Introduction Keyframe authority remains readable and valid. Automated decisions gain explicit synthesis/validation provenance and remain fail-closed.

Provider adapters must expose real capabilities and may not claim native timed-reference support merely to bypass synthesis. LTX-2.5 Candidate C uses synthesized Introduction Keyframes.

ProductionTask retry authority remains unchanged because internal span executions are orchestration work inside one governed editorial Shot, not independent ProductionTasks or hidden retries.

Automated validation is an execution gate, not a replacement for Timed Asset Presence authority. Timing is never inferred from prose.

## Rejected alternatives

Keep manual two-image approval for every introduction: rejected because it defeats episode-scale automation.

Infer asset entrance frames from prompt prose: rejected because it would create hidden production authority.

Treat every internal span as a new ProductionTask: rejected because it changes the editorial Shot model, dependency graph and retry semantics.

Skip boundary validation after automated synthesis: rejected because generated images can drift in identity, composition, camera or asset count.

## Validation

Acceptance requires static/type tests, Phase 3.1-3.5 regressions, UI validation, a real configured boundary image-edit workflow, and live SHT-002 proof that Ros is absent through frame 95 and introduced automatically from frame 96 without manual boundary-image preparation.
