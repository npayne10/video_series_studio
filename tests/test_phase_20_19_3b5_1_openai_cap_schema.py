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
