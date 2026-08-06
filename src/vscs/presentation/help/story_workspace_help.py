"""Comprehensive context-sensitive help for the Story Workspace."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)


class StoryWorkspaceHelpDialog(QDialog):
    """Explain the Story-first VSCS workflow and Story governance controls."""

    SECTIONS: tuple[tuple[str, str], ...] = (
        (
            "Overview",
            "<h2>Story Workspace</h2>"
            "<p>The Story Workspace is the starting point for every VSCS production. "
            "The Story defines the creative truth; Productions, Scenes, Shots, assets, "
            "prompts and rendered video are derived from it.</p>"
            "<p><b>Relationship:</b> Story → Production → Scene → Shot → Output.</p>",
        ),
        (
            "Story Lifecycle",
            "<h2>Story Lifecycle</h2>"
            "<ul>"
            "<li><b>Draft:</b> Original Story being created or edited.</li>"
            "<li><b>Imported:</b> Story registered from an external source file.</li>"
            "<li><b>Analysed:</b> Story structure and metadata reviewed.</li>"
            "<li><b>Approved:</b> Accepted as Story Canon.</li>"
            "<li><b>Locked:</b> Canon protected from ordinary editing.</li>"
            "<li><b>Archived:</b> Retained but removed from active work.</li>"
            "</ul>",
        ),
        (
            "Story Metadata",
            "<h2>Story Metadata</h2>"
            "<p><b>Title:</b> Story name. <b>Description:</b> short working description. "
            "<b>Source Type:</b> source format. <b>Source Path:</b> manuscript file. "
            "<b>Synopsis:</b> narrative summary. <b>Genres:</b> classification. "
            "<b>Themes:</b> central ideas. <b>Target Audience:</b> intended viewers. "
            "<b>Language:</b> primary language. <b>Author:</b> creator. "
            "<b>Estimated Runtime:</b> preliminary screen duration. "
            "<b>Keywords:</b> search terms. <b>Notes:</b> editorial or production notes.</p>",
        ),
        (
            "Story Governance",
            "<h2>Story Governance</h2>"
            "<ul>"
            "<li><b>Mark Analysed:</b> confirms review of the Story definition.</li>"
            "<li><b>Approve:</b> establishes Story Canon.</li>"
            "<li><b>Lock:</b> protects approved Canon.</li>"
            "<li><b>Unlock:</b> permits controlled access while retaining approval.</li>"
            "<li><b>Reopen:</b> returns Canon to revision state.</li>"
            "<li><b>Archive/Restore:</b> removes or returns a Story to active use.</li>"
            "</ul>",
        ),
        (
            "Source Files",
            "<h2>Source Files</h2>"
            "<p>Use <b>Browse…</b> to select DOCX, PDF, Markdown, TXT or Final Draft "
            "files. VSCS records the selected path and detects the source type from "
            "the file extension. Selecting a file does not yet perform Story Analysis; "
            "that belongs to the next workflow stage.</p>",
        ),
        (
            "Production Workflow",
            "<h2>Story-driven Production Workflow</h2>"
            "<pre>Idea\n  ↓\nStory\n  ↓\nStory Analysis\n  ↓\nStory Approval\n  ↓\n"
            "Production Planning\n  ↓\nAssets and CAPs\n  ↓\nScenes and Shots\n  ↓\n"
            "Prompt Generation\n  ↓\nRendering\n  ↓\n"
            "Lip-sync and Post Production\n  ↓\nRelease</pre>",
        ),
        (
            "Best Practices",
            "<h2>Best Practices</h2>"
            "<ul>"
            "<li>Capture the complete Story before defining a Production.</li>"
            "<li>Complete core metadata before approval.</li>"
            "<li>Approve and lock Canon before large-scale production work.</li>"
            "<li>Reopen the Story formally when Canon changes are required.</li>"
            "<li>Use one canonical Story as the source for multiple Productions.</li>"
            "</ul>",
        ),
        (
            "Physical Reality",
            "<h2>Physical Reality</h2>"
            "<p>Science-fiction visuals must remain grounded in defined reality. "
            "Gravity, inertia, momentum, material behaviour, lighting, biology and "
            "engineering remain internally consistent unless the Story Canon defines "
            "an explicit exception. A different planet may have different gravity, but "
            "Earth gravity remains 1G within the production universe.</p>",
        ),
        (
            "Related Workspaces",
            "<h2>Related Workspaces</h2>"
            "<p>Future contextual links will connect Story Analysis, Production "
            "Planning, Asset Manager, CAP Manager, Scene Editor, Shot Planner and "
            "Prompt Graph help.</p>",
        ),
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("storyWorkspaceHelpDialog")
        self.setWindowTitle("VSCS Help — Story Workspace")
        self.resize(820, 620)

        self.section_list = QListWidget(self)
        self.section_list.setObjectName("storyWorkspaceHelpSections")
        self.content = QTextBrowser(self)
        self.content.setObjectName("storyWorkspaceHelpContent")
        self.content.setOpenExternalLinks(False)

        for title, html in self.SECTIONS:
            item = QListWidgetItem(title)
            item.setData(256, html)
            self.section_list.addItem(item)

        self.section_list.currentItemChanged.connect(self._show_section)
        self.section_list.setCurrentRow(0)

        body = QHBoxLayout()
        body.addWidget(self.section_list, 1)
        body.addWidget(self.content, 3)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.close)

        layout = QVBoxLayout(self)
        layout.addLayout(body, 1)
        layout.addWidget(buttons)

    def _show_section(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        """Display the selected help section."""
        self.content.setHtml("" if current is None else str(current.data(256)))
