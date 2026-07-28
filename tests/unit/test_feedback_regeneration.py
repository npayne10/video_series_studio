"""Tests for Phase 11.7.3 evaluation-feedback regeneration."""

from vscs.presentation.widgets.cap_reference_regeneration import _feedback, _request_from_manifest


def test_feedback_merges_pre_siee_and_violations_without_duplicates() -> None:
    pre = {"recommendations": ["Remove hull lettering.", "Strengthen spacecraft silhouette."]}
    siee = {
        "recommendations": ["Remove hull lettering.", "Avoid maritime bridge forms."],
        "violations": ["Prominent non-canonical insignia."],
    }

    result = _feedback(pre, siee)

    assert result == (
        "Remove hull lettering.",
        "Strengthen spacecraft silhouette.",
        "Avoid maritime bridge forms.",
        "Correct this detected violation: Prominent non-canonical insignia.",
    )


def test_request_from_manifest_uses_new_seed_and_preserves_render_settings() -> None:
    request = _request_from_manifest(
        {
            "prompt": "Original compiled prompt",
            "negative_prompt": "text, watermark",
            "model": "Qwen Image 2512 via XCIC",
            "seed": 41,
            "width": 1664,
            "height": 928,
        }
    )

    assert request.seed == 42
    assert request.width == 1664
    assert request.height == 928
    assert request.variations == 1
    assert request.model == "Qwen Image 2512 via XCIC"
