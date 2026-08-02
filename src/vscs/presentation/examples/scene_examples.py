"""Structured smart examples for Scene Editor data entry."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExampleTopic:
    """Practical entry guidance for one VSCS field or empty state."""

    topic_id: str
    placeholder: str = ""
    inline_tip: str = ""
    examples: tuple[str, ...] = ()
    empty_state: str = ""
    completion_hint: str = ""


SCENE_EXAMPLES = (
    ExampleTopic(
        topic_id="scene.name",
        placeholder="Example: Arrival at Xorix",
        inline_tip="Use a short, descriptive title that is easy to recognise.",
        examples=(
            "Arrival at Xorix",
            "The Impossible Signal",
            "Descent into Bulbateen",
            "Return to the Mauritania",
        ),
    ),
    ExampleTopic(
        topic_id="scene.heading",
        placeholder="Example: EXT. XORIX ORBIT - DAY",
        inline_tip="Use screenplay format: INT./EXT. LOCATION - TIME.",
        examples=(
            "EXT. XORIX ORBIT - DAY",
            "INT. MAURITANIA BRIDGE - NIGHT",
            "INT. SHUTTLE - CONTINUOUS",
            "EXT. FOREST CLEARING - DUSK",
        ),
        completion_hint="Begin with INT. or EXT. to see heading suggestions.",
    ),
    ExampleTopic(
        topic_id="scene.summary",
        placeholder=(
            "Describe the story event. Example: The crew enters orbit around Xorix "
            "and sees the planet for the first time."
        ),
        inline_tip="Describe the story event and dramatic change, not camera work.",
    ),
    ExampleTopic(
        topic_id="scene.participants",
        inline_tip="Select every visible or speaking Character asset.",
        empty_state=(
            "No Character assets are available. Open Asset Manager and create or import "
            "Character assets before assigning participants."
        ),
    ),
    ExampleTopic(
        topic_id="scene.dialogue",
        placeholder="Example: We're receiving an unexpected signal.",
        inline_tip="Select a participant as speaker, then add the spoken line.",
        empty_state=(
            "Select scene participants first. Dialogue speakers must be participants."
        ),
    ),
    ExampleTopic(
        topic_id="scene.required_assets",
        inline_tip="Select ships, props, technology, effects and other visible dependencies.",
        empty_state=(
            "No production assets are available. Add assets in Asset Manager before "
            "declaring scene dependencies."
        ),
    ),
    ExampleTopic(
        topic_id="scene.duration",
        inline_tip="Estimate the complete scene runtime, not the duration of one shot.",
    ),
)
