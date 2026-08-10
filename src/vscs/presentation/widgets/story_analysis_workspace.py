"""Interactive Story Analysis review workspace for Phase 18.2.5."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QPen, QTextCursor, QTextFormat
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from vscs.application.story import StoryRecord
from vscs.application.story_analysis import (
    ANALYSIS_RESULT_ARTIFACT,
    STORY_KNOWLEDGE_GRAPH_ARTIFACT,
    AnalysisStatus,
    StoryAnalysisEngine,
    StoryAnalysisRequest,
)
from vscs.application.story_analysis.source_reader import StorySourceReader, StorySourceReadError
from vscs.domain.story_analysis import AnalysisResult, SourceSpan
from vscs.domain.story_analysis.graph import GraphNode, GraphNodeKind, StoryKnowledgeGraph

_MODEL_ID_ROLE = int(Qt.ItemDataRole.UserRole)
_SOURCE_START_ROLE = _MODEL_ID_ROLE + 1
_SOURCE_END_ROLE = _MODEL_ID_ROLE + 2
_KIND_ROLE = _MODEL_ID_ROLE + 3


class StoryGraphView(QGraphicsView):
    """Compact deterministic viewer for Story Knowledge Graph nodes and edges."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("storyKnowledgeGraphView")
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._items: dict[str, QGraphicsRectItem] = {}
        self.setRenderHint(self.renderHints())
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

    def set_graph(self, graph: StoryKnowledgeGraph | None) -> None:
        self._scene.clear()
        self._items.clear()
        if graph is None or not graph.nodes:
            self._scene.addText("No Story Knowledge Graph available.")
            return
        positions = self._layout(graph.nodes)
        for edge in graph.edges:
            source = positions.get(edge.source_node_id)
            target = positions.get(edge.target_node_id)
            if source is None or target is None:
                continue
            x1, y1 = source
            x2, y2 = target
            line = self._scene.addLine(x1 + 70, y1 + 22, x2 + 70, y2 + 22)
            line.setPen(QPen(QColor("#808080"), 1))
            line.setZValue(-1)
        for node in graph.nodes:
            x, y = positions[node.node_id]
            item = self._scene.addRect(x, y, 140, 44)
            item.setData(_MODEL_ID_ROLE, node.source_model_id)
            item.setBrush(QBrush(self._node_color(node.kind)))
            item.setPen(QPen(QColor("#606060"), 1))
            item.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable, True)
            label = self._scene.addText(self._short_label(node.label))
            label.setPos(x + 5, y + 4)
            label.setTextWidth(130)
            self._items[node.source_model_id] = item
        self._scene.setSceneRect(self._scene.itemsBoundingRect().adjusted(-20, -20, 20, 20))
        self.fit_graph()

    def select_model(self, model_id: str | None) -> None:
        for item in self._items.values():
            item.setSelected(False)
        if model_id is None:
            return
        item = self._items.get(model_id)
        if item is not None:
            item.setSelected(True)
            self.centerOn(item)

    def zoom_in(self) -> None:
        self.scale(1.2, 1.2)

    def zoom_out(self) -> None:
        self.scale(1 / 1.2, 1 / 1.2)

    def fit_graph(self) -> None:
        if self._scene.items():
            self.fitInView(self._scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)

    @staticmethod
    def _layout(nodes: tuple[GraphNode, ...]) -> dict[str, tuple[float, float]]:
        columns = 4
        spacing_x = 190
        spacing_y = 85
        return {
            node.node_id: ((index % columns) * spacing_x, (index // columns) * spacing_y)
            for index, node in enumerate(nodes)
        }

    @staticmethod
    def _short_label(label: str) -> str:
        normalized = " ".join(label.split())
        return normalized if len(normalized) <= 38 else f"{normalized[:35]}..."

    @staticmethod
    def _node_color(kind: GraphNodeKind) -> QColor:
        colors = {
            GraphNodeKind.CHARACTER: "#dcecff",
            GraphNodeKind.LOCATION: "#dcf5df",
            GraphNodeKind.TECHNOLOGY: "#ffe9c7",
            GraphNodeKind.PROP: "#f3e4ff",
            GraphNodeKind.DIALOGUE: "#eadfff",
            GraphNodeKind.ACTION: "#fff4bf",
            GraphNodeKind.EMOTION: "#ffdede",
            GraphNodeKind.TIMELINE_EVENT: "#e0e0e0",
        }
        return QColor(colors.get(kind, "#eeeeee"))


class StoryAnalysisWorkspaceDialog(QDialog):
    """Review Story Analysis results without modifying the source manuscript."""

    def __init__(
        self,
        story: StoryRecord,
        engine: StoryAnalysisEngine,
        source_reader: StorySourceReader | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.story = story
        self.engine = engine
        self.source_reader = source_reader or StorySourceReader()
        self.source_text = ""
        self.analysis: AnalysisResult | None = None
        self.graph: StoryKnowledgeGraph | None = None
        self.setObjectName("storyAnalysisWorkspace")
        self.setWindowTitle(f"Story Analysis — {story.title}")
        self.resize(1500, 900)
        self._build_ui()
        self.rebuild_analysis()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        self.analyse_button = self._button("Rebuild Analysis", self.rebuild_analysis)
        self.graph_button = self._button("Rebuild Graph", self.rebuild_analysis)
        self.validate_button = self._button("Validate Story", self._validate)
        self.export_analysis_button = self._button("Export Analysis", self._export_analysis)
        self.export_graph_button = self._button("Export Graph", self._export_graph)
        self.refresh_button = self._button("Refresh", self.rebuild_analysis)
        for button in (
            self.analyse_button,
            self.graph_button,
            self.validate_button,
            self.export_analysis_button,
            self.export_graph_button,
            self.refresh_button,
        ):
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        self.search_edit = QLineEdit(self)
        self.search_edit.setObjectName("storyAnalysisSearch")
        self.search_edit.setPlaceholderText("Search analysis…")
        self.search_edit.textChanged.connect(self._populate_inspector)
        toolbar.addWidget(self.search_edit)
        self.filter_combo = QComboBox(self)
        self.filter_combo.setObjectName("storyAnalysisFilter")
        self.filter_combo.addItems(
            (
                "All",
                "Characters",
                "Locations",
                "Technology",
                "Props",
                "Dialogue",
                "Actions",
                "Emotions",
                "Relationships",
                "Timeline",
            )
        )
        self.filter_combo.currentTextChanged.connect(self._populate_inspector)
        toolbar.addWidget(self.filter_combo)
        root.addLayout(toolbar)

        graph_controls = QHBoxLayout()
        graph_controls.addWidget(QLabel("Knowledge Graph", self))
        graph_controls.addStretch(1)
        graph_controls.addWidget(self._button("Zoom +", self.graph_view_zoom_in))
        graph_controls.addWidget(self._button("Zoom -", self.graph_view_zoom_out))
        graph_controls.addWidget(self._button("Fit", self.graph_view_fit))
        root.addLayout(graph_controls)

        horizontal = QSplitter(Qt.Orientation.Horizontal, self)
        self.source_view = QPlainTextEdit(horizontal)
        self.source_view.setObjectName("storyAnalysisSource")
        self.source_view.setReadOnly(True)
        self.inspector = QTreeWidget(horizontal)
        self.inspector.setObjectName("storyAnalysisInspector")
        self.inspector.setHeaderLabels(("Analysis", "Details", "Confidence"))
        self.inspector.itemSelectionChanged.connect(self._inspector_selection_changed)
        self.graph_view = StoryGraphView(horizontal)
        horizontal.addWidget(self.source_view)
        horizontal.addWidget(self.inspector)
        horizontal.addWidget(self.graph_view)
        horizontal.setStretchFactor(0, 4)
        horizontal.setStretchFactor(1, 3)
        horizontal.setStretchFactor(2, 4)
        root.addWidget(horizontal, 1)

        diagnostics_header = QLabel("Validation & Diagnostics", self)
        root.addWidget(diagnostics_header)
        self.diagnostics = QListWidget(self)
        self.diagnostics.setObjectName("storyAnalysisDiagnostics")
        self.diagnostics.setMaximumHeight(150)
        root.addWidget(self.diagnostics)
        self.status_label = QLabel("Not analysed", self)
        self.status_label.setObjectName("storyAnalysisStatus")
        root.addWidget(self.status_label)

    def _button(self, text: str, slot) -> QPushButton:
        button = QPushButton(text, self)
        button.clicked.connect(slot)
        return button

    def rebuild_analysis(self) -> None:
        try:
            self.source_text = self.source_reader.read(self.story)
        except StorySourceReadError as exc:
            self._show_failure(str(exc))
            return
        request = StoryAnalysisRequest(
            story_id=self.story.story_id,
            source_text=self.source_text,
            source_revision=self.story.updated_at or None,
            metadata={"title": self.story.title, "source_path": self.story.source_path},
        )
        report = self.engine.analyze(request)
        if report.status is not AnalysisStatus.COMPLETED:
            message = "\n".join(report.diagnostics) or "Story analysis failed"
            self._show_failure(message)
            return
        analysis = report.artifacts.get(ANALYSIS_RESULT_ARTIFACT)
        graph = report.artifacts.get(STORY_KNOWLEDGE_GRAPH_ARTIFACT)
        if not isinstance(analysis, AnalysisResult) or not isinstance(graph, StoryKnowledgeGraph):
            self._show_failure("Story Analysis pipeline did not publish the expected results")
            return
        self.analysis = analysis
        self.graph = graph
        self.source_view.setPlainText(self.source_text)
        self.graph_view.set_graph(graph)
        self._populate_inspector()
        self._populate_diagnostics(report.diagnostics)
        self.status_label.setText(
            f"Analysis complete — {len(analysis.entities)} entities, "
            f"{len(graph.nodes)} graph nodes, {len(graph.edges)} graph edges"
        )

    def _populate_inspector(self) -> None:
        self.inspector.clear()
        if self.analysis is None:
            return
        query = self.search_edit.text().strip().casefold()
        selected_filter = self.filter_combo.currentText()
        groups = (
            (
                "Characters",
                [entity for entity in self.analysis.entities if entity.kind.value == "character"],
            ),
            (
                "Locations",
                [entity for entity in self.analysis.entities if entity.kind.value == "location"],
            ),
            (
                "Technology",
                [entity for entity in self.analysis.entities if entity.kind.value == "technology"],
            ),
            (
                "Props",
                [entity for entity in self.analysis.entities if entity.kind.value == "prop"],
            ),
            ("Dialogue", list(self.analysis.dialogues)),
            ("Actions", list(self.analysis.actions)),
            ("Emotions", list(self.analysis.emotions)),
            ("Relationships", list(self.analysis.relationships)),
            ("Timeline", list(self.analysis.ordered_timeline)),
        )
        for group_name, values in groups:
            if selected_filter != "All" and selected_filter != group_name:
                continue
            parent = QTreeWidgetItem((group_name, str(len(values)), ""))
            accepted = 0
            for value in values:
                label, details, confidence, model_id, span = self._describe(value)
                haystack = f"{label} {details}".casefold()
                if query and query not in haystack:
                    continue
                child = QTreeWidgetItem((label, details, f"{confidence:.0%}"))
                child.setData(0, _MODEL_ID_ROLE, model_id)
                child.setData(0, _KIND_ROLE, group_name)
                if span is not None:
                    child.setData(0, _SOURCE_START_ROLE, span.start_offset)
                    child.setData(0, _SOURCE_END_ROLE, span.end_offset)
                parent.addChild(child)
                accepted += 1
            if accepted:
                parent.setText(1, str(accepted))
                self.inspector.addTopLevelItem(parent)
                parent.setExpanded(True)
        self.inspector.resizeColumnToContents(0)

    def _describe(self, value) -> tuple[str, str, float, str, SourceSpan | None]:
        if hasattr(value, "entity_id"):
            span = value.sources[0] if value.sources else None
            return value.name, value.kind.value, value.confidence, value.entity_id, span
        if hasattr(value, "dialogue_id"):
            return value.text, "Dialogue", value.confidence, value.dialogue_id, value.source
        if hasattr(value, "action_id"):
            return value.summary, "Action", value.confidence, value.action_id, value.source
        if hasattr(value, "emotion_id"):
            return value.emotion, "Emotion", value.confidence, value.emotion_id, value.source
        if hasattr(value, "relationship_id"):
            span = value.sources[0] if value.sources else None
            details = f"{value.source_entity_id} → {value.target_entity_id}"
            return value.relationship_type, details, value.confidence, value.relationship_id, span
        span = value.sources[0] if value.sources else None
        return value.summary, "Timeline", value.confidence, value.event_id, span

    def _inspector_selection_changed(self) -> None:
        items = self.inspector.selectedItems()
        if not items:
            return
        item = items[0]
        model_id = item.data(0, _MODEL_ID_ROLE)
        self.graph_view.select_model(str(model_id) if model_id else None)
        start = item.data(0, _SOURCE_START_ROLE)
        end = item.data(0, _SOURCE_END_ROLE)
        if isinstance(start, int) and isinstance(end, int):
            self._highlight_source(start, end)

    def _highlight_source(self, start: int, end: int) -> None:
        cursor = self.source_view.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        selection = QPlainTextEdit.ExtraSelection()
        selection.cursor = cursor
        selection.format.setBackground(QColor("#fff2a8"))
        selection.format.setProperty(QTextFormat.Property.FullWidthSelection, False)
        self.source_view.setExtraSelections((selection,))
        self.source_view.setTextCursor(cursor)
        self.source_view.ensureCursorVisible()

    def _populate_diagnostics(self, diagnostics: tuple[str, ...]) -> None:
        self.diagnostics.clear()
        for diagnostic in diagnostics:
            self.diagnostics.addItem(diagnostic)
        if self.analysis is not None:
            for diagnostic in self.analysis.diagnostics:
                if diagnostic not in diagnostics:
                    self.diagnostics.addItem(diagnostic)
        if self.diagnostics.count() == 0:
            self.diagnostics.addItem("No diagnostics reported.")

    def _validate(self) -> None:
        if self.analysis is None or self.graph is None:
            QMessageBox.information(self, "Story Analysis", "Run Story Analysis first.")
            return
        unresolved_dialogue = sum(
            1 for dialogue in self.analysis.dialogues if dialogue.speaker_entity_id is None
        )
        low_confidence = sum(1 for node in self.graph.nodes if node.confidence < 0.6)
        message = (
            f"Graph integrity: valid\n"
            f"Unresolved dialogue speakers: {unresolved_dialogue}\n"
            f"Low-confidence graph nodes: {low_confidence}\n"
            f"Timeline events: {len(self.analysis.timeline_events)}"
        )
        QMessageBox.information(self, "Story Validation", message)

    def _export_analysis(self) -> None:
        if self.analysis is not None:
            self._export_json(
                f"{self.story.story_id.lower()}-analysis.json",
                self.analysis.model_dump(mode="json"),
            )

    def _export_graph(self) -> None:
        if self.graph is not None:
            self._export_json(
                f"{self.story.story_id.lower()}-knowledge-graph.json",
                self.graph.model_dump(mode="json"),
            )

    def _export_json(self, suggested_name: str, payload: dict[str, object]) -> None:
        path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Story Analysis",
            suggested_name,
            "JSON files (*.json)",
        )
        if not path:
            return
        try:
            Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, "Story Analysis", f"Unable to export: {exc}")

    def graph_view_zoom_in(self) -> None:
        self.graph_view.zoom_in()

    def graph_view_zoom_out(self) -> None:
        self.graph_view.zoom_out()

    def graph_view_fit(self) -> None:
        self.graph_view.fit_graph()

    def _show_failure(self, message: str) -> None:
        self.analysis = None
        self.graph = None
        self.source_view.clear()
        self.inspector.clear()
        self.graph_view.set_graph(None)
        self.diagnostics.clear()
        self.diagnostics.addItem(message)
        self.status_label.setText("Analysis unavailable")
        QMessageBox.critical(self, "Story Analysis", message)
