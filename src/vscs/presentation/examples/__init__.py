"""Public API for reusable VSCS smart field examples."""

from .adaptive_examples import heading_suggestions, scene_name_examples
from .empty_state_examples import EMPTY_STATE_FALLBACK, empty_state_text
from .example_provider import ExampleContext, ExampleProvider
from .scene_examples import ExampleTopic, SCENE_EXAMPLES

__all__ = [
    "EMPTY_STATE_FALLBACK",
    "ExampleContext",
    "ExampleProvider",
    "ExampleTopic",
    "SCENE_EXAMPLES",
    "empty_state_text",
    "heading_suggestions",
    "scene_name_examples",
]
