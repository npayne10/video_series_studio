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


def test_openai_model_list_reads_api_visible_ids(monkeypatch):
    from types import SimpleNamespace

    from vscs.infrastructure.ai import openai_provider

    models = (
        SimpleNamespace(id="gpt-6.1-terra"),
        SimpleNamespace(id="gpt-6-luna"),
        SimpleNamespace(id="gpt-6.1-terra"),
    )
    monkeypatch.setattr(
        openai_provider,
        "import_module",
        lambda _name: SimpleNamespace(
            OpenAI=lambda **_kw: SimpleNamespace(
                models=SimpleNamespace(list=lambda: SimpleNamespace(data=models))
            )
        ),
    )
    assert openai_provider.OpenAICAPGenerationProvider.list_available_models(
        api_key="unit-test-key"
    ) == ("gpt-6-luna", "gpt-6.1-terra")


def test_settings_model_dropdown_preserves_current_and_accepts_manual(qtbot, monkeypatch):
    from types import SimpleNamespace

    from vscs.infrastructure.configuration import AIProvider, ApplicationSettings
    from vscs.presentation.dialogs import settings_dialog

    class FakeCredentials:
        def get_openai_api_key(self):
            return "unit-test-key"

    monkeypatch.setattr(settings_dialog, "AICredentialStore", FakeCredentials)
    config = SimpleNamespace(settings=ApplicationSettings(), save=lambda: None)
    config.settings.ai.provider = AIProvider.OPENAI
    config.settings.ai.openai_model = "gpt-6.1-terra"
    dialog = settings_dialog.SettingsDialog(config)
    qtbot.addWidget(dialog)

    assert dialog.openai_model.isEditable()
    assert dialog.openai_model.currentText() == "gpt-6.1-terra"
    dialog.openai_model.setCurrentText("manually-entered-model")
    assert dialog.openai_model.currentText() == "manually-entered-model"


def test_settings_model_refresh_is_nonblocking(qtbot, monkeypatch):
    from threading import Event
    from types import SimpleNamespace

    from PySide6.QtWidgets import QDialogButtonBox

    from vscs.infrastructure.configuration import AIProvider, ApplicationSettings
    from vscs.presentation.dialogs import settings_dialog

    class FakeCredentials:
        def get_openai_api_key(self):
            return "unit-test-key"

    monkeypatch.setattr(settings_dialog, "AICredentialStore", FakeCredentials)
    config = SimpleNamespace(settings=ApplicationSettings(), save=lambda: None)
    config.settings.ai.provider = AIProvider.OPENAI
    config.settings.ai.openai_model = "gpt-6.1-terra"
    dialog = settings_dialog.SettingsDialog(config)
    qtbot.addWidget(dialog)
    started = Event()
    release = Event()

    def fetch(*, api_key):
        assert api_key == "unit-test-key"
        started.set()
        assert release.wait(5)
        return ("gpt-6-luna", "gpt-6.1-terra")

    monkeypatch.setattr(settings_dialog.OpenAICAPGenerationProvider, "list_available_models", fetch)
    dialog.refresh_openai_models_button.click()
    qtbot.waitUntil(started.is_set, timeout=3000)
    assert not dialog._settings_buttons.button(QDialogButtonBox.StandardButton.Save).isEnabled()
    release.set()
    qtbot.waitUntil(lambda: dialog._model_discovery is None, timeout=5000)
    assert dialog.openai_model.count() == 2
    assert dialog.openai_model.currentText() == "gpt-6.1-terra"


def test_settings_connection_checks_selected_dropdown_model(qtbot, monkeypatch):
    from types import SimpleNamespace

    from vscs.infrastructure.configuration import AIProvider, ApplicationSettings
    from vscs.presentation.dialogs import settings_dialog

    class FakeCredentials:
        def get_openai_api_key(self):
            return "unit-test-key"

    monkeypatch.setattr(settings_dialog, "AICredentialStore", FakeCredentials)
    config = SimpleNamespace(settings=ApplicationSettings(), save=lambda: None)
    config.settings.ai.provider = AIProvider.OPENAI
    config.settings.ai.openai_model = "gpt-6.1-terra"
    dialog = settings_dialog.SettingsDialog(config)
    qtbot.addWidget(dialog)
    checked = []
    monkeypatch.setattr(
        settings_dialog.OpenAICAPGenerationProvider,
        "test_connection",
        lambda **kw: checked.append(kw["model"]),
    )
    monkeypatch.setattr(settings_dialog.QMessageBox, "information", lambda *_args: None)
    dialog._test_openai_connection()
    assert checked == ["gpt-6.1-terra"]


def test_cap_identity_quality_rejects_single_shot_indicator_action():
    from vscs.infrastructure.ai.openai_provider import OpenAICAPGenerationProvider

    draft = GeneratedCAPDraft(
        title="Engineering control room",
        canonical_description="An empty engineering control room.",
        visual_identity="Fixed diagnostic console beside a workstation.",
        continuity_rules=("Have the small indicator pulse once, then return to steady.",),
    )
    assert OpenAICAPGenerationProvider._identity_quality_issues(draft)
    corrected = draft.model_copy(
        update={
            "continuity_rules": ("Maintain the fixed console beside the workstation across shots.",)
        }
    )
    assert OpenAICAPGenerationProvider._identity_quality_issues(corrected) == ()


def test_cap_event_quality_guard_regenerates_draft_only_once(monkeypatch):
    from vscs.domain.caps.generation import (
        CanonicalFactExtraction,
        CAPCanonAnalysis,
        CAPGenerationRequest,
    )
    from vscs.infrastructure.ai.openai_provider import OpenAICAPGenerationProvider

    provider = object.__new__(OpenAICAPGenerationProvider)
    request = CAPGenerationRequest(
        asset_id="STORY-LOC-001",
        asset_name="Engineering control room",
        asset_category="location",
        story_context="The indicator pulses once and returns to steady glow.",
    )
    calls = []
    transient = GeneratedCAPDraft(
        title="Engineering control room",
        canonical_description="The indicator pulses once.",
        visual_identity="The engineering control room contains a fixed diagnostic console.",
    )
    stable = GeneratedCAPDraft(
        title="Engineering control room",
        canonical_description="An empty engineering control room.",
        visual_identity="The engineering control room contains a fixed diagnostic console.",
        continuity_rules=("Preserve console placement.",),
    )
    monkeypatch.setattr(
        provider,
        "_extract_facts",
        lambda _request: CanonicalFactExtraction(),
    )
    monkeypatch.setattr(
        provider,
        "_analyse_canon",
        lambda _request, _facts: CAPCanonAnalysis(),
    )

    def draft_stage(_request, _analysis, *, corrections=()):
        calls.append(corrections)
        return transient if len(calls) == 1 else stable

    monkeypatch.setattr(provider, "_generate_draft", draft_stage)
    assert provider.generate_cap(request) == stable
    assert len(calls) == 2
    assert calls[0] == ()
    assert "Shot-specific" in calls[1][0]


def test_cap_unresolved_transient_after_retry_refuses_result(monkeypatch):
    import pytest

    from vscs.domain.caps.generation import (
        CanonicalFactExtraction,
        CAPCanonAnalysis,
        CAPGenerationRequest,
    )
    from vscs.infrastructure.ai.openai_provider import OpenAICAPGenerationProvider
    from vscs.infrastructure.ai.provider import AIProviderError

    provider = object.__new__(OpenAICAPGenerationProvider)
    request = CAPGenerationRequest(
        asset_id="STORY-LOC-001",
        asset_name="Engineering control room",
        asset_category="location",
        story_context="A single indicator pulse.",
    )
    transient = GeneratedCAPDraft(
        title="Engineering room",
        canonical_description="The indicator pulses once then returns to a steady glow.",
        visual_identity="A fixed console.",
    )
    calls = []
    monkeypatch.setattr(provider, "_extract_facts", lambda _request: CanonicalFactExtraction())
    monkeypatch.setattr(
        provider,
        "_analyse_canon",
        lambda _request, _facts: CAPCanonAnalysis(),
    )

    def draft_stage(_request, _analysis, *, corrections=()):
        calls.append(corrections)
        return transient

    monkeypatch.setattr(provider, "_generate_draft", draft_stage)
    with pytest.raises(AIProviderError, match="quality gate failed"):
        provider.generate_cap(request)
    assert len(calls) == 2


def test_cap_generation_instructions_separate_identity_from_shot_events(monkeypatch):
    from vscs.domain.caps.generation import (
        CAPCanonAnalysis,
        CAPGenerationRequest,
    )
    from vscs.infrastructure.ai.openai_provider import (
        OpenAICAPGenerationProvider,
        _StrictCAPConfidence,
        _StrictGeneratedCAPDraft,
    )

    provider = object.__new__(OpenAICAPGenerationProvider)
    request = CAPGenerationRequest(
        asset_id="STORY-LOC-001",
        asset_name="Engineering control room",
        asset_category="location",
        story_context="A console's display glows blue.",
    )
    captured = {}

    def parse(*, instructions, input_text, result_type, stage):
        captured.update(instructions=instructions, input_text=input_text, stage=stage)
        return _StrictGeneratedCAPDraft(
            title="Engineering room",
            canonical_description="The engineering room is empty.",
            visual_identity="Console beside workstation.",
            production_notes="",
            continuity_rules=("Preserve fixed placement.",),
            prohibited_variations=(),
            functional_capabilities=(),
            semantic_tags=(),
            production_classifications=(),
            behaviour_references=(),
            production_metadata=(),
            unresolved_questions=(),
            source_summary="",
            canonical_facts=(),
            contradictions=(),
            confidence=dict.fromkeys(_StrictCAPConfidence.model_fields, 0.5),
        )

    monkeypatch.setattr(provider, "_parse", parse)
    provider._generate_draft(request, CAPCanonAnalysis())
    assert "Single-occurrence actions" in captured["instructions"]
    assert "preserve unambiguous ownership" in captured["instructions"].lower()
    assert "do not promote those events" in captured["input_text"]


def test_cap_stable_identity_needs_no_extra_paid_draft_pass(monkeypatch):
    from vscs.domain.caps.generation import (
        CanonicalFactExtraction,
        CAPCanonAnalysis,
        CAPGenerationRequest,
    )
    from vscs.infrastructure.ai.openai_provider import OpenAICAPGenerationProvider

    provider = object.__new__(OpenAICAPGenerationProvider)
    request = CAPGenerationRequest(
        asset_id="STORY-LOC-001",
        asset_name="Engineering control room",
        asset_category="location",
        story_context="A diagnostic console stands beside a workstation.",
    )
    stable = GeneratedCAPDraft(
        title="Engineering room",
        canonical_description="An empty engineering control room.",
        visual_identity="The engineering control room contains a console beside the workstation.",
        continuity_rules=("Preserve their fixed positions.",),
    )
    calls = []
    monkeypatch.setattr(provider, "_extract_facts", lambda _request: CanonicalFactExtraction())
    monkeypatch.setattr(provider, "_analyse_canon", lambda _request, _facts: CAPCanonAnalysis())

    def draft_stage(_request, _analysis, *, corrections=()):
        calls.append(corrections)
        return stable

    monkeypatch.setattr(provider, "_generate_draft", draft_stage)
    assert provider.generate_cap(request) == stable
    assert calls == [()]


def test_cap_source_grounding_detects_lost_console_display_relationship():
    from vscs.domain.caps.generation import CAPGenerationRequest
    from vscs.infrastructure.ai.openai_provider import OpenAICAPGenerationProvider

    request = CAPGenerationRequest(
        asset_id="STORY-LOC-001",
        asset_name="Engineering control room",
        asset_category="location",
        story_context=(
            "A diagnostic console stands beside a workstation. "
            "The diagnostic console's blue display glows steadily. "
            "A small indicator pulses once."
        ),
    )
    incorrect = GeneratedCAPDraft(
        title="Engineering room",
        canonical_description="A diagnostic console stands beside a workstation.",
        visual_identity=(
            "The room contains a blue display and a small indicator. "
            "Their ownership and the indicator's location are unspecified."
        ),
    )
    issues = OpenAICAPGenerationProvider._source_relationship_issues(request, incorrect)
    assert len(issues) == 1
    assert "do not invent" in issues[0]
    corrected = incorrect.model_copy(
        update={
            "visual_identity": (
                "The diagnostic console beside the workstation has a blue display. "
                "The small indicator's attachment remains unresolved."
            )
        }
    )
    assert OpenAICAPGenerationProvider._source_relationship_issues(request, corrected) == ()


def test_cap_source_grounding_does_not_invent_unspecified_display_owner():
    from vscs.domain.caps.generation import CAPGenerationRequest
    from vscs.infrastructure.ai.openai_provider import OpenAICAPGenerationProvider

    request = CAPGenerationRequest(
        asset_id="STORY-LOC-001",
        asset_name="Engineering control room",
        asset_category="location",
        story_context="A room contains a diagnostic console and a separate blue display.",
    )
    draft = GeneratedCAPDraft(
        title="Engineering room",
        canonical_description="Room with equipment.",
        visual_identity="The display's ownership is unspecified.",
    )
    assert OpenAICAPGenerationProvider._source_relationship_issues(request, draft) == ()


def test_cap_grounding_quality_gate_requests_at_most_one_corrective_pass(monkeypatch):
    from vscs.domain.caps.generation import (
        CanonicalFactExtraction,
        CAPCanonAnalysis,
        CAPGenerationRequest,
    )
    from vscs.infrastructure.ai.openai_provider import OpenAICAPGenerationProvider

    provider = object.__new__(OpenAICAPGenerationProvider)
    request = CAPGenerationRequest(
        asset_id="STORY-LOC-001",
        asset_name="Engineering control room",
        asset_category="location",
        story_context=(
            "A diagnostic console stands beside a workstation. "
            "The diagnostic console's blue display glows steadily."
        ),
    )
    first = GeneratedCAPDraft(
        title="Engineering room",
        canonical_description="The room contains a console beside a workstation.",
        visual_identity="The blue display's ownership is unspecified.",
    )
    corrected = first.model_copy(
        update={
            "visual_identity": (
                "The engineering control room contains a diagnostic console with a blue display."
            )
        }
    )
    calls = []
    monkeypatch.setattr(provider, "_extract_facts", lambda _request: CanonicalFactExtraction())
    monkeypatch.setattr(provider, "_analyse_canon", lambda _request, _facts: CAPCanonAnalysis())

    def draft_stage(_request, _analysis, *, corrections=()):
        calls.append(corrections)
        return first if len(calls) == 1 else corrected

    monkeypatch.setattr(provider, "_generate_draft", draft_stage)
    assert provider.generate_cap(request) == corrected
    assert len(calls) == 2
    assert "blue display" in calls[1][0]


def test_cap_draft_generation_rechecks_original_story_text(monkeypatch):
    from vscs.domain.caps.generation import CAPCanonAnalysis, CAPGenerationRequest
    from vscs.infrastructure.ai.openai_provider import (
        OpenAICAPGenerationProvider,
        _StrictCAPConfidence,
        _StrictGeneratedCAPDraft,
    )

    provider = object.__new__(OpenAICAPGenerationProvider)
    request = CAPGenerationRequest(
        asset_id="STORY-LOC-001",
        asset_name="Engineering control room",
        asset_category="location",
        story_context="The diagnostic console's blue display glows steadily.",
    )
    observed = {}

    def parse(*, instructions, input_text, result_type, stage):
        observed.update(input_text=input_text, stage=stage)
        return _StrictGeneratedCAPDraft(
            title="Engineering room",
            canonical_description="An engineering room.",
            visual_identity="Console and workstation.",
            production_notes="",
            continuity_rules=(),
            prohibited_variations=(),
            functional_capabilities=(),
            semantic_tags=(),
            production_classifications=(),
            behaviour_references=(),
            production_metadata=(),
            unresolved_questions=(),
            source_summary="",
            canonical_facts=(),
            contradictions=(),
            confidence=dict.fromkeys(_StrictCAPConfidence.model_fields, 0.5),
        )

    monkeypatch.setattr(provider, "_parse", parse)
    provider._generate_draft(request, CAPCanonAnalysis())
    assert request.story_context in observed["input_text"]
    assert "source-grounding cross-check" in observed["input_text"]


def test_cap_ambiguous_pronoun_does_not_force_console_ownership():
    from vscs.domain.caps.generation import CAPGenerationRequest
    from vscs.infrastructure.ai.openai_provider import OpenAICAPGenerationProvider

    request = CAPGenerationRequest(
        asset_id="STORY-LOC-001",
        asset_name="Engineering control room",
        asset_category="location",
        story_context="A diagnostic console stands beside a workstation, its blue display glowing steadily.",
    )
    draft = GeneratedCAPDraft(
        title="Engineering room",
        canonical_description="Engineering room with a console and a workstation.",
        visual_identity="The blue display's owner is uncertain.",
    )
    assert OpenAICAPGenerationProvider._source_relationship_issues(request, draft) == ()


def test_b525_ship_identity_gate_repairs_interior_prop_substitution(monkeypatch):
    from vscs.domain.caps.generation import (
        CanonicalFactExtraction,
        CAPCanonAnalysis,
        CAPGenerationRequest,
    )
    from vscs.infrastructure.ai.openai_provider import OpenAICAPGenerationProvider

    provider = object.__new__(OpenAICAPGenerationProvider)
    request = CAPGenerationRequest(
        asset_id="STORY-SHI-001",
        asset_name="Unmanned exploration vessel",
        asset_category="ship",
        story_context="Inside an unmanned exploration vessel is an engineering control room.",
    )
    incorrect = GeneratedCAPDraft(
        title="Unmanned exploration vessel",
        canonical_description="An unmanned exploration vessel contains a control room.",
        visual_identity=(
            "The diagnostic console has a blue display. "
            "A small indicator is present, but no exterior appearance is established."
        ),
        continuity_rules=("Keep the control room aboard the unmanned vessel.",),
    )
    fixed = incorrect.model_copy(
        update={
            "visual_identity": "The vessel's exterior silhouette remains unresolved.",
            "continuity_rules": (
                "The vessel contains an engineering control room.",
                "A separate diagnostic console is inside the room.",
            ),
        }
    )
    calls = []
    monkeypatch.setattr(provider, "_extract_facts", lambda _request: CanonicalFactExtraction())
    monkeypatch.setattr(provider, "_analyse_canon", lambda _request, _facts: CAPCanonAnalysis())

    def draft_stage(_request, _analysis, *, corrections=()):
        calls.append(corrections)
        return incorrect if len(calls) == 1 else fixed

    monkeypatch.setattr(provider, "_generate_draft", draft_stage)
    assert provider.generate_cap(request) == fixed
    assert len(calls) == 2
    assert "silhouette" in " ".join(calls[1]).lower()


def test_b525_ship_identity_gate_rejects_repeat_substitution(monkeypatch):
    import pytest

    from vscs.domain.caps.generation import (
        CanonicalFactExtraction,
        CAPCanonAnalysis,
        CAPGenerationRequest,
    )
    from vscs.infrastructure.ai.openai_provider import OpenAICAPGenerationProvider
    from vscs.infrastructure.ai.provider import AIProviderError

    provider = object.__new__(OpenAICAPGenerationProvider)
    request = CAPGenerationRequest(
        asset_id="STORY-SHI-001",
        asset_name="Unmanned exploration vessel",
        asset_category="ship",
        story_context="A ship has an internal engineering control room.",
    )
    invalid = GeneratedCAPDraft(
        title="Unmanned exploration vessel",
        canonical_description="An unmanned ship contains a room.",
        visual_identity="The diagnostic console has a blue display.",
    )
    calls = []
    monkeypatch.setattr(provider, "_extract_facts", lambda _request: CanonicalFactExtraction())
    monkeypatch.setattr(provider, "_analyse_canon", lambda _request, _facts: CAPCanonAnalysis())

    def draft_stage(_request, _analysis, *, corrections=()):
        calls.append(corrections)
        return invalid

    monkeypatch.setattr(provider, "_generate_draft", draft_stage)
    with pytest.raises(AIProviderError, match="quality gate failed after one"):
        provider.generate_cap(request)
    assert len(calls) == 2
