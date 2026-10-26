"""Prevent OpenAI 400 invalid_json_schema for the CAP Draft wire model."""

from vscs.domain.caps.generation import GeneratedCAPDraft
from vscs.infrastructure.ai.openai_provider import (
    _StrictCAPConfidence,
    _StrictGeneratedCAPDraft,
)


def test_cap_wire_schema_requires_all_declared_properties():
    schema = _StrictGeneratedCAPDraft.model_json_schema()
    assert set(schema["properties"]) == set(schema["required"])
    assert "production_metadata" in schema["required"]
    confidence = _StrictCAPConfidence.model_json_schema()
    assert set(confidence["properties"]) == set(confidence["required"])


def test_cap_wire_response_round_trips_to_legacy_domain_defaults():
    payload = {
        "title": "Control Room",
        "canonical_description": "Enclosed room",
        "visual_identity": "Fixed console",
        "production_notes": "",
        "continuity_rules": [],
        "prohibited_variations": [],
        "functional_capabilities": [],
        "semantic_tags": [],
        "production_classifications": [],
        "behaviour_references": [],
        "production_metadata": [],
        "unresolved_questions": [],
        "source_summary": "",
        "canonical_facts": [],
        "contradictions": [],
        "confidence": dict.fromkeys(_StrictCAPConfidence.model_fields, 0.0),
    }
    wire = _StrictGeneratedCAPDraft.model_validate(payload)
    wire_data = wire.model_dump()
    wire_data["production_metadata"] = {
        entry.key: entry.value for entry in wire.production_metadata
    }
    domain = GeneratedCAPDraft.model_validate(wire_data)
    assert domain.production_metadata == {}
    assert domain.title == "Control Room"
