"""Constants used by the CAR repository verifier."""

REPOSITORY_VERSION = "2.0"
DEFAULT_MANIFEST = "manifest.json"
DEFAULT_PROFILE = "profile.json"
DEFAULT_BEHAVIOUR = "behaviour.json"
DEFAULT_DESCRIPTION = "description.md"
CANON_FOLDER = "canon"
PROMPTS_FOLDER = "prompts"
METADATA_FOLDER = "metadata"
TESTS_FOLDER = "tests"

VISUAL_METADATA_FILES = (
    "cap.json",
    "knowledge.json",
    "history.json",
    "evaluation.json",
    "provenance.json",
)
VISUAL_REQUIRED_DIRECTORIES = (
    "canon",
    "metadata",
    "prompts",
    "thumbnails",
    "candidates",
    "rejected",
)
CONFIGURATION_REQUIRED_FILES = ("profile.json", "description.md")
BEHAVIOUR_REQUIRED_DIRECTORIES = ("prompts", "tests")
BEHAVIOUR_REQUIRED_FILES = ("behaviour.json",)
SUPPORTED_IMAGE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff",
}
