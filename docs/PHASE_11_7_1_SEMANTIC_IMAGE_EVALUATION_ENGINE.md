# Phase 11.7.1 — Semantic Image Evaluation Engine (SIEE) v1.0

SIEE adds vision-capable semantic quality control to the Canonical Asset pipeline. It complements CIEE's deterministic local technical checks.

## Evaluation dimensions

- Prompt adherence
- Asset category validity
- Unwanted visible text, logos, captions, watermarks and UI overlays
- Canon and visual-identity consistency
- Engineering plausibility
- Cinematic production quality

Each dimension receives a 0–100 score, concise evidence, and an optional blocking flag. A blocking semantic failure forces a `REGENERATE` decision even when the numeric average is high.

## Decisions

- `PASS`: overall semantic score of at least 80 with no blocking failures
- `REVIEW`: score from 55 to 79 with no blocking failures
- `REGENERATE`: score below 55 or any blocking failure

## Canon comparison

When an approved Primary image exists for the same CAP, SIEE submits it as a second image and asks the evaluator to compare silhouette, identity, proportions, materials, colours and design language.

## Provider

SIEE v1.0 uses the OpenAI Responses API with structured output and image input. It reuses the API key and model configured in **VSCS Settings**. The image is sent as a base64 data URL; no temporary public URL is created.

## User interface

Select an image in the Canonical Reference Gallery and click **Semantic Evaluate Selected…**. The report displays the semantic decision, overall score, provider/model, metric results, detected features, violations and recommendations.

Reports are stored under:

```text
<Project>\Canonical Assets\<ASSET-ID>\.metadata\evaluation\<IMAGE>.siee.json
```

## Privacy and cost

Semantic evaluation sends the selected candidate image, CAP facts, generation prompt and—when available—the approved Primary reference to the configured external AI provider. It therefore requires an API key and may incur provider usage charges.

## Relationship to CIEE

CIEE and SIEE remain separate reports in v1.0:

```text
Candidate Image
  ├─ CIEE technical report
  └─ SIEE semantic report
```

A later combined Production Readiness Report will merge both scores and decisions into one approval recommendation.
