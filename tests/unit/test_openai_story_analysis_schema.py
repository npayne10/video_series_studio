"""Regression coverage for the OpenAI Story Analysis Structured Outputs schema."""

from vscs.infrastructure.ai.story_analysis_provider import _OpenAIStoryAnalysisResponse


def _assert_strict_objects(schema: dict, root: dict) -> None:
    if "$ref" in schema:
        reference = schema["$ref"].removeprefix("#/$defs/")
        schema = root["$defs"][reference]
    if schema.get("type") == "object":
        properties = schema.get("properties", {})
        assert set(schema.get("required", ())) == set(properties)
        assert schema.get("additionalProperties") is False
        for child in properties.values():
            _assert_strict_objects(child, root)
    if schema.get("type") == "array":
        _assert_strict_objects(schema.get("items", {}), root)
    for variant in schema.get("anyOf", ()):
        _assert_strict_objects(variant, root)


def test_openai_story_analysis_schema_requires_every_object_property() -> None:
    schema = _OpenAIStoryAnalysisResponse.model_json_schema()

    _assert_strict_objects(schema, schema)


def test_openai_story_analysis_wire_model_converts_attributes_to_domain_mapping() -> None:
    response = _OpenAIStoryAnalysisResponse.model_validate(
        {
            "entities": [
                {
                    "name": "Iron Horizon",
                    "category": "ship",
                    "description": "Survey vessel",
                    "aliases": [],
                    "evidence_text": ["The Iron Horizon entered orbit."],
                    "attributes": [
                        {"key": "role", "value": "survey vessel"},
                    ],
                    "confidence": 0.97,
                }
            ],
            "metadata": {
                "summary": "Arrival in orbit.",
                "themes": ["discovery"],
                "tone": ["awe"],
                "setting": ["orbit"],
                "production_notes": [],
                "confidence": 0.91,
            },
        }
    )

    domain = response.to_domain()

    assert domain.entities[0].attributes == {"role": "survey vessel"}
    assert domain.metadata.summary == "Arrival in orbit."
    assert domain.diagnostics == ("OpenAI Story Analysis provider used",)
