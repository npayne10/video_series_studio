"""F5.4.2: compact stage-matrix layout, preserving selection/action pairing."""

from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from vscs.presentation.widgets.cap_visual_candidate_quality import (
    _review_matrix_section,
)


def test_matrix_section_keeps_drop_down_beside_action(qtbot):
    host = QWidget()
    qtbot.addWidget(host)
    outer = QVBoxLayout(host)
    grid = _review_matrix_section(outer, "C2.1 - persisted sessions", "reviewSessionsMatrix")
    combo = QComboBox()
    combo.setObjectName("c21SavedHumanReviewChoices")
    action = QPushButton("Resume Selected Human Review (No Generation)")
    action.setObjectName("c21ResumeHumanReview")
    grid.addWidget(combo, 0, 1)
    grid.addWidget(action, 0, 2)

    group = host.findChild(QGroupBox, "reviewSessionsMatrix")
    assert group is not None
    assert group.title() == "C2.1 - persisted sessions"
    assert group.layout() is grid
    assert grid.itemAtPosition(0, 1).widget() is combo
    assert grid.itemAtPosition(0, 2).widget() is action
    assert combo.parentWidget() is group
    assert action.parentWidget() is group
    assert grid.columnStretch(1) == 1


def test_two_stage_matrices_preserve_order_and_independent_controls(qtbot):
    host = QWidget()
    qtbot.addWidget(host)
    outer = QVBoxLayout(host)
    stage_b = _review_matrix_section(outer, "Stage B", "reviewStageBMatrix")
    stage_c1 = _review_matrix_section(outer, "Stage C1", "reviewC1Matrix")
    field = QComboBox()
    field.setObjectName("spatialEvidenceStatus")
    inspect = QPushButton("Inspect Stage C Governed Handoff (No Generation)")
    inspect.setObjectName("stageCGovernedCorrectionInspect")
    stage_b.addWidget(field, 0, 1)
    stage_c1.addWidget(inspect, 0, 2)

    first = host.findChild(QGroupBox, "reviewStageBMatrix")
    second = host.findChild(QGroupBox, "reviewC1Matrix")
    assert first is not None
    assert second is not None
    assert outer.itemAt(0).widget() is first
    assert outer.itemAt(1).widget() is second
    assert stage_b.itemAtPosition(0, 1).widget() is field
    assert stage_c1.itemAtPosition(0, 2).widget() is inspect
    assert field.objectName() == "spatialEvidenceStatus"
    assert inspect.objectName() == "stageCGovernedCorrectionInspect"
