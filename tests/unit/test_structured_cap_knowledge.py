"""Unit coverage for Phase 19.1 structured CAP production knowledge."""

from vscs.domain.caps import (
    CanonicalConstraintKind,
    KnowledgeAuthority,
    PersistedCanonicalConstraint,
    PersistedCanonicalFact,
    PersistedFunctionalCapability,
    StructuredCAPKnowledge,
    is_production_authority,
)


def test_structured_knowledge_normalizes_terms_and_preserves_authority() -> None:
    knowledge = StructuredCAPKnowledge(
        facts=(
            PersistedCanonicalFact(
                key="class",
                value="Survey Vessel",
                source="Author",
                authority=KnowledgeAuthority.CANONICAL,
            ),
        ),
        functional_identity=(
            PersistedFunctionalCapability(
                capability="Orbital flight",
                authority=KnowledgeAuthority.APPROVED,
            ),
        ),
        constraints=(
            PersistedCanonicalConstraint(
                kind=CanonicalConstraintKind.FORBIDDEN,
                rule="Do not change hull markings",
                authority=KnowledgeAuthority.PROPOSED,
            ),
        ),
        semantic_tags=("ship", " ship ", "survey"),
        production_metadata={" source ": " author "},
    )

    assert knowledge.semantic_tags == ("ship", "survey")
    assert knowledge.production_metadata == {"source": "author"}
    assert is_production_authority(knowledge.facts[0].authority)
    assert is_production_authority(knowledge.functional_identity[0].authority)
    assert not is_production_authority(knowledge.constraints[0].authority)
