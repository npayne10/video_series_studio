"""Shared governed video-provider capability-validation scenarios."""

from vscs.domain.provider_capability_validation import ValidationCriterion, ValidationScenario


def standard_video_validation_scenarios() -> tuple[ValidationScenario, ...]:
    """Return the provider-neutral video-generation validation scenario set."""

    return (
        ValidationScenario(
            scenario_id="text-to-video-baseline",
            label="Text-to-video baseline",
            description=(
                "Validate prompt adherence, visual coherence and production-usable "
                "baseline quality without reference-image conditioning."
            ),
            criteria=(
                ValidationCriterion(
                    "prompt-adherence",
                    "Prompt adherence",
                    "Primary subject, setting and action follow the supplied production intent.",
                ),
                ValidationCriterion(
                    "temporal-coherence",
                    "Temporal coherence",
                    "Motion remains coherent without disruptive flicker, warping or identity drift.",
                ),
                ValidationCriterion(
                    "production-quality",
                    "Production quality",
                    "Output is technically and visually usable for the intended production tier.",
                ),
            ),
        ),
        ValidationScenario(
            scenario_id="image-to-video-reference-fidelity",
            label="Image-to-video reference fidelity",
            description=(
                "Validate that an authoritative visual reference remains recognisable "
                "through the generated shot."
            ),
            criteria=(
                ValidationCriterion(
                    "reference-fidelity",
                    "Reference fidelity",
                    "Core identity, design and distinguishing reference features are preserved.",
                ),
                ValidationCriterion(
                    "motion-without-redesign",
                    "Motion without redesign",
                    "Animation introduces motion without materially redesigning the reference.",
                ),
                ValidationCriterion(
                    "reference-temporal-stability",
                    "Reference temporal stability",
                    "Reference-defining features remain stable across the evaluated output.",
                ),
            ),
        ),
        ValidationScenario(
            scenario_id="camera-motion-control",
            label="Camera and motion control",
            description=(
                "Validate controlled cinematic camera behaviour and physically credible "
                "subject motion."
            ),
            criteria=(
                ValidationCriterion(
                    "camera-intent",
                    "Camera intent",
                    "Camera movement follows the requested framing and movement intent.",
                ),
                ValidationCriterion(
                    "motion-physics",
                    "Motion physics",
                    "Subject and environmental motion remain physically credible.",
                ),
                ValidationCriterion(
                    "shot-stability",
                    "Shot stability",
                    "The shot avoids unintended jumps, framing collapse and disruptive motion artifacts.",
                ),
            ),
        ),
        ValidationScenario(
            scenario_id="subject-continuity",
            label="Character and subject continuity",
            description=(
                "Validate identity and design continuity for production subjects across "
                "a sustained generated shot."
            ),
            criteria=(
                ValidationCriterion(
                    "identity-continuity",
                    "Identity continuity",
                    "Character or subject identity remains stable throughout the output.",
                ),
                ValidationCriterion(
                    "wardrobe-design-continuity",
                    "Wardrobe/design continuity",
                    "Wardrobe, equipment and defining design features remain consistent.",
                ),
                ValidationCriterion(
                    "anatomy-geometry-stability",
                    "Anatomy/geometry stability",
                    "Anatomy and rigid geometry avoid material deformation or unexplained mutation.",
                ),
            ),
        ),
        ValidationScenario(
            scenario_id="complex-production-shot",
            label="Complex production shot",
            description=(
                "Validate production realism when multiple subjects, environment, camera "
                "and action requirements must remain coherent together."
            ),
            criteria=(
                ValidationCriterion(
                    "multi-element-adherence",
                    "Multi-element adherence",
                    "Required subjects, environment and action elements are all represented coherently.",
                ),
                ValidationCriterion(
                    "spatial-consistency",
                    "Spatial consistency",
                    "Relative placement, scale and scene geometry remain credible over time.",
                ),
                ValidationCriterion(
                    "production-realism",
                    "Production realism",
                    "The combined result meets the project's grounded cinematic realism threshold.",
                ),
            ),
        ),
    )
