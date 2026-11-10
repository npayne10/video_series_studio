"""Qt UI acceptance: existing Draft CAP revision is separate from CAP creation."""

from types import SimpleNamespace
from unittest.mock import Mock

from PySide6.QtWidgets import QMessageBox

from vscs.domain.caps import CAPStatus
from vscs.presentation.dialogs import story_cap_batch_dialog as ui


def _dialog(qtbot, monkeypatch):
    projects = SimpleNamespace(project_directory=None)
    caps = SimpleNamespace(
        assets=SimpleNamespace(projects=projects),
        get=Mock(return_value=SimpleNamespace(status=CAPStatus.DRAFT)),
    )
    generator = SimpleNamespace(caps=caps, provider=Mock())
    stories = SimpleNamespace(
        list_stories=lambda: (
            SimpleNamespace(story_id="STORY-001", title="Disposable", status=ui.StoryStatus.APPROVED),
        )
    )
    monkeypatch.setattr(ui, "StoryLifecycleService", lambda _projects: stories)
    monkeypatch.setattr(ui, "StoryCAPSpecificationService", lambda *_a: Mock())
    monkeypatch.setattr(ui, "CAPStructuredSpecificationService", lambda *_a: Mock())
    candidates = (
        SimpleNamespace(
            asset_id="STORY-PRO-TEST",
            name="Diagnostic Console",
            category="prop",
            has_cap=True,
            has_specification=True,
        ),
    )
    service = SimpleNamespace(
        discover=Mock(return_value=candidates),
        batch=Mock(),
    )
    monkeypatch.setattr(ui, "StoryCAPBatchReviewService", lambda _batch: service)
    dialog = ui.StoryCAPBatchDialog(generator)
    qtbot.addWidget(dialog)
    return dialog, service, caps


def test_existing_specification_only_in_revision_selector(qtbot, monkeypatch):
    dialog, service, caps = _dialog(qtbot, monkeypatch)
    dialog.discover()
    assert dialog.assets.count() == 0
    assert not dialog.preview.isEnabled()
    assert not dialog.regenerate.isEnabled()
    assert dialog.existing_assets.count() == 1
    assert dialog.existing_assets.currentData() == "STORY-PRO-TEST"
    assert dialog.edit_existing.isEnabled()
    assert "Already specified" in dialog.summary.toPlainText()
    service.discover.assert_called_once_with("STORY-001")
    caps.get.assert_called_once_with("STORY-PRO-TEST")


def test_revision_action_does_not_generate_provider_work(qtbot, monkeypatch):
    dialog, service, _caps = _dialog(qtbot, monkeypatch)
    dialog.discover()
    snapshot = SimpleNamespace(asset_id="STORY-PRO-TEST")
    prepare = Mock(return_value=snapshot)
    monkeypatch.setattr(ui, "prepare_draft_cap_revision", prepare)
    editor = Mock()
    editor.exec.return_value = 0  # Operator cancelled
    factory = Mock(return_value=editor)
    monkeypatch.setattr(ui, "EditExistingDraftCAPDialog", factory)
    dialog.edit_existing.click()
    prepare.assert_called_once_with(service, "STORY-001", "STORY-PRO-TEST")
    factory.assert_called_once_with(service, snapshot, dialog)
    dialog.generator.provider.generate.assert_not_called()


def test_existing_approved_cap_not_selectable(qtbot, monkeypatch):
    dialog, _service, caps = _dialog(qtbot, monkeypatch)
    caps.get.return_value.status = CAPStatus.APPROVED
    dialog.discover()
    assert dialog.existing_assets.count() == 0
    assert not dialog.edit_existing.isEnabled()


def test_revision_preflight_failure_is_visible_and_non_mutating(qtbot, monkeypatch):
    dialog, service, caps = _dialog(qtbot, monkeypatch)
    dialog.discover()
    monkeypatch.setattr(
        ui, "prepare_draft_cap_revision", Mock(side_effect=RuntimeError("Stale Draft"))
    )
    notice = Mock()
    monkeypatch.setattr(QMessageBox, "warning", notice)
    dialog.edit_existing.click()
    notice.assert_called_once()
    assert "Stale Draft" in notice.call_args.args[2]
    caps.get.assert_called_once()
    service.batch.generator.save_reviewed.assert_not_called()
