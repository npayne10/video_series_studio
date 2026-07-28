# Phase 11.8 — CAIE Knowledge Base & Category Intelligence

## Status

Implemented as Canonical Asset Intelligence Engine v2.0.

## Purpose

CAIE v2 replaces prompt-only category hints with a data-driven design intelligence layer. It resolves an asset category and, where possible, a specialised archetype before compiling the final XCIC prompt.

## Rendering path

```text
CAP
  -> CAIE Knowledge Resolver
  -> Category and Archetype Knowledge
  -> Engineering Principles
  -> Xorix Style Knowledge
  -> Evaluation Feedback
  -> Final Positive and Negative Prompts
  -> XCIC Core / ComfyUI
```

## Knowledge packages

Knowledge is stored as YAML under:

```text
src/vscs/application/caie/knowledge/
```

Initial packages include:

- `ships/orbital_tug.yaml`
- `ships/generic_spacecraft.yaml`
- `characters/generic_character.yaml`
- `vehicles/generic_vehicle.yaml`
- `locations/generic_location.yaml`
- `environments/generic_environment.yaml`
- `planets/generic_planet.yaml`
- `props/generic_prop.yaml`
- `technology/generic_technology.yaml`
- `generic_asset.yaml`
- `styles/xorix_grounded_scifi.yaml`

## Orbital tug correction

When a Ship CAP contains terms such as `tug`, `tow craft`, or `towing craft`, CAIE resolves `ships/orbital_tug`.

The package establishes:

- an orbital spacecraft operating in vacuum;
- reaction-control thrusters and docking hardpoints;
- credible load paths, heat rejection and rendezvous sensors;
- a dry orbital environment;
- a complete three-quarter production view.

It explicitly forbids:

- maritime wheelhouses and harbour-boat bridges;
- masts, rigging, funnels and smokestacks;
- anchors, rudders, keels and marine propellers;
- waterlines, bow waves, wet hulls and open weather decks;
- harbour tugboat, fishing-vessel and ocean-ship archetypes;
- readable hull names, registration numbers and decorative insignia.

## Knowledge schema

Each design package contains:

- classification;
- purpose;
- required features;
- engineering principles;
- preferred semantic language;
- forbidden visible features;
- forbidden archetypes;
- negative terms;
- required prompt anchors;
- environment guidance;
- composition guidance.

Style packages contain reusable positive language and negative terms.

## Resolution and safety

The resolver chooses the most specific known archetype, then falls back to category knowledge, then to `generic_asset`.

CAIE validates required anchors before rendering. Missing anchors stop generation rather than silently submitting an ambiguous prompt.

Legacy style identifiers `grounded_cinematic` and `neutral_reference` resolve to the Xorix grounded hard-science-fiction style package for compatibility.

## Provenance

Generation manifests now record:

```json
{
  "prompt_engine": "Canonical Asset Intelligence Engine v2.0",
  "knowledge_profile": "ships/orbital_tug",
  "style_profile": "xorix_grounded_scifi"
}
```

## Extension model

New knowledge can be added without changing the prompt compiler. Add a YAML package and extend the resolver only when a new specialised archetype needs keyword or metadata selection.

Future packages may include exploration carriers, survey vessels, shuttles, stations, character roles, Builder technology and Zagkron design language.
