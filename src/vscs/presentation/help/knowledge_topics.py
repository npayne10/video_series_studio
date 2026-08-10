"""Structured knowledge topics for the VSCS Knowledge Framework."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class KnowledgeTopic:
    """Reusable explanatory content for one VSCS concept or control."""

    topic_id: str
    title: str
    purpose: str
    description: str
    examples: tuple[str, ...] = ()
    common_mistakes: tuple[str, ...] = ()
    related_topics: tuple[str, ...] = ()
    documentation_page: str | None = None


SCENE_TOPICS = (
    KnowledgeTopic(
        topic_id="scene.name",
        title="Scene Name",
        purpose="Provides a short, readable name for the scene.",
        description=(
            "Use a concise title that helps people recognise the scene in the Story "
            "Browser. This is separate from the screenplay heading."
        ),
        examples=("Arrival at Xorix", "The Impossible Signal"),
        common_mistakes=("Repeating the full screenplay heading as the scene name.",),
        related_topics=("scene.heading", "scene.sequence"),
        documentation_page="docs/story/scene_editor.md#scene-name",
    ),
    KnowledgeTopic(
        topic_id="scene.episode",
        title="Episode ID",
        purpose="Identifies the episode that owns this scene.",
        description=(
            "Use the canonical episode identity. The scene ID is generated from the "
            "episode ID and scene sequence."
        ),
        examples=("EP-001", "EP-010"),
        common_mistakes=("Using an episode title instead of its canonical ID.",),
        related_topics=("scene.sequence", "scene.name"),
        documentation_page="docs/story/scene_editor.md#episode-and-sequence",
    ),
    KnowledgeTopic(
        topic_id="scene.sequence",
        title="Scene Sequence",
        purpose="Controls the scene's order within its episode.",
        description=(
            "Sequence numbers should be unique within an episode and should follow the "
            "intended story order."
        ),
        examples=("1", "7", "24"),
        common_mistakes=("Giving two scenes in the same episode the same sequence.",),
        related_topics=("scene.episode", "scene.transition"),
        documentation_page="docs/story/scene_editor.md#episode-and-sequence",
    ),
    KnowledgeTopic(
        topic_id="scene.heading",
        title="Scene Heading",
        purpose="Defines interior or exterior, location and story time.",
        description=(
            "Use a screenplay-style heading. It gives SSIE a compact production context "
            "for planning shots and continuity."
        ),
        examples=(
            "INT. MAURITANIA BRIDGE - NIGHT",
            "EXT. XORIX SPACEPORT - DUSK",
        ),
        common_mistakes=("Using a narrative sentence instead of a screenplay heading.",),
        related_topics=("scene.location", "scene.time"),
        documentation_page="docs/story/scene_editor.md#heading",
    ),
    KnowledgeTopic(
        topic_id="scene.location",
        title="Primary Location",
        purpose="Defines the canonical place where the scene occurs.",
        description=(
            "Choose exactly one Location or Environment asset as the primary setting. "
            "Additional locations or environmental dependencies belong under Required Assets."
        ),
        examples=(
            "LOC-XORIX-SPACEPORT",
            "LOC-MAURITANIA-BRIDGE",
            "ENV-XORIX-FOREST",
        ),
        common_mistakes=(
            "Typing an asset name instead of selecting its canonical ID.",
            "Selecting a prop as the primary location.",
        ),
        related_topics=("scene.required_assets", "scene.heading"),
        documentation_page="docs/story/scene_editor.md#location",
    ),
    KnowledgeTopic(
        topic_id="scene.summary",
        title="Scene Summary",
        purpose="Explains what changes in the scene and why it matters.",
        description=(
            "Write a concise narrative summary focused on the scene's dramatic purpose. "
            "SSIE uses it to infer scene intent and shot coverage."
        ),
        examples=("The crew enters orbit around Xorix and sees the planet for the first time.",),
        common_mistakes=("Listing camera instructions instead of the story event.",),
        related_topics=("scene.heading", "scene.dialogue"),
        documentation_page="docs/story/scene_editor.md#summary",
    ),
    KnowledgeTopic(
        topic_id="scene.participants",
        title="Participants",
        purpose="Lists every character who appears in the scene.",
        description=(
            "Select Character assets for all visible or speaking participants. Dialogue "
            "speakers must be selected here first."
        ),
        examples=("CHR-JAMES", "CHR-SANDRA", "CHR-VAREX"),
        common_mistakes=(
            "Leaving out a character who speaks.",
            "Adding ships or props as participants.",
        ),
        related_topics=("scene.dialogue", "scene.required_assets"),
        documentation_page="docs/story/scene_editor.md#participants",
    ),
    KnowledgeTopic(
        topic_id="scene.dialogue",
        title="Dialogue",
        purpose="Stores ordered spoken lines and performance direction.",
        description=(
            "Choose a selected participant as speaker, enter the spoken line, and add an "
            "optional performance note. Reorder lines to match the scene."
        ),
        examples=("CHR-JAMES [quietly]: We should not be here.",),
        common_mistakes=(
            "Adding dialogue before selecting the speaker as a participant.",
            "Putting camera direction in the performance note.",
        ),
        related_topics=("scene.participants", "scene.summary"),
        documentation_page="docs/story/scene_editor.md#dialogue",
    ),
    KnowledgeTopic(
        topic_id="scene.required_assets",
        title="Required Assets",
        purpose="Declares production assets needed to stage the scene.",
        description=(
            "Select every non-character asset required by the scene, including ships, "
            "vehicles, props, effects, technology and secondary environments."
        ),
        examples=("SHP-IRON-HORIZON", "PROP-BRIDGE-CONSOLE", "FX-JUMP"),
        common_mistakes=(
            "Adding participants here instead of in the Participants selector.",
            "Omitting a visible prop needed for continuity.",
        ),
        related_topics=("scene.location", "scene.participants"),
        documentation_page="docs/story/scene_editor.md#required-assets",
    ),
    KnowledgeTopic(
        topic_id="scene.time",
        title="Time of Day",
        purpose="Defines the scene's lighting and temporal continuity context.",
        description=(
            "Choose the closest controlled time value. Use Continuous when the scene "
            "continues immediately from the preceding scene."
        ),
        examples=("Dawn", "Dusk", "Night", "Continuous"),
        common_mistakes=("Using Continuous for an unrelated later scene.",),
        related_topics=("scene.heading", "scene.transition"),
        documentation_page="docs/story/scene_editor.md#time-of-day",
    ),
    KnowledgeTopic(
        topic_id="scene.transition",
        title="Transition",
        purpose="Defines how editing enters this scene.",
        description=(
            "Cut is the normal choice. Use Dissolve, Fade or Match Cut only when the "
            "transition has a deliberate narrative or temporal purpose."
        ),
        examples=("Cut", "Dissolve", "Fade In", "Match Cut"),
        common_mistakes=("Using decorative transitions on every scene.",),
        related_topics=("scene.time", "scene.sequence"),
        documentation_page="docs/story/scene_editor.md#transition",
    ),
    KnowledgeTopic(
        topic_id="scene.duration",
        title="Estimated Duration",
        purpose="Estimates the complete runtime of the scene.",
        description=(
            "Select a common preset or enter a custom duration. VSCS uses the estimate to "
            "calculate an indicative shot count and frame count."
        ),
        examples=("30 seconds", "60 seconds", "120 seconds"),
        common_mistakes=("Entering the duration of one shot instead of the whole scene.",),
        related_topics=("scene.summary", "scene.dialogue"),
        documentation_page="docs/story/scene_editor.md#duration",
    ),
)
