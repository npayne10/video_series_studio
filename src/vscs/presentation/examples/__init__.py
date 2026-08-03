"""Public API for reusable VSCS smart field examples."""

from .adaptive_examples import heading_suggestions, scene_name_examples
from .empty_state_examples import EMPTY_STATE_FALLBACK, empty_state_text
from .example_provider import ExampleContext, ExampleProvider
from .scene_examples import SCENE_EXAMPLES, ExampleTopic

__all__ = [
    "EMPTY_STATE_FALLBACK",
    "SCENE_EXAMPLES",
    "ExampleContext",
    "ExampleProvider",
    "ExampleTopic",
    "empty_state_text",
    "heading_suggestions",
    "scene_name_examples",
]
