"""Batch Story CAP proposal review, with deliberate per-item persistence."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from vscs.application.caps.generator import CAPGeneratorService
from vscs.application.caps.proposal_cache import CAPProposalCache, cache_fingerprint
from vscs.application.caps.story_batch import (
    StoryBatchError,
    StoryBatchProposal,
    StoryCAPBatchService,
)
from vscs.application.caps.story_batch_review import StoryCAPBatchReviewService
from vscs.application.caps.story_specification import StoryCAPSpecificationService
from vscs.application.caps.structured_specification import CAPStructuredSpecificationService
from vscs.application.story.lifecycle import StoryLifecycleService, StoryStatus
from vscs.presentation.dialogs.cap_detail_review_dialog import CAPDetailReviewDialog
from vscs.presentation.dialogs.story_cap_specification_dialog import (
    StoryCAPSpecificationDialog,
)


class StoryCAPBatchDialog(QDialog):
    """Operator-controlled queue; rejected/cancelled proposals never write."""

    def __init__(self, generator: CAPGeneratorService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Approved Story → CAP Batch Review")
        self.setMinimumSize(760, 490)
        caps = generator.caps
        self.generator = generator
        self.stories = StoryLifecycleService(caps.assets.projects)
        proposal_service = StoryCAPSpecificationService(
            generator, CAPStructuredSpecificationService(caps)
        )
        self.review_service = StoryCAPBatchReviewService(
            StoryCAPBatchService(self.stories, proposal_service)
        )
        self._proposal_cache: dict[tuple[str, str, str, str, str], StoryBatchProposal] = {}
        self.cache = (
            CAPProposalCache(caps.assets.projects.project_directory)
            if caps.assets.projects.project_directory is not None
            else None
        )
        self.story = QComboBox()
        for story in self.stories.list_stories():
            if story.status in {StoryStatus.APPROVED, StoryStatus.LOCKED}:
                self.story.addItem(f"{story.story_id} — {story.title}", story.story_id)
        self.assets = QComboBox()
        self.inspect = QPushButton("Discover Shot Assets")
        self.preview = QPushButton("Review / Generate Proposal")
        self.regenerate = QPushButton("Regenerate Using AI (Paid)")
        self.close_button = QPushButton("Close")
        self.summary = QTextEdit()
        self.summary.setReadOnly(True)
        self.summary.setPlainText(
            "Select an approved Story. Discovery reads only persisted Shot asset bindings. "
            "Each generated proposal requires review and separate confirmation. "
            "Only Draft CAP records may be created; nothing is approved."
        )
        row = QHBoxLayout()
        row.addWidget(self.inspect)
        row.addWidget(self.assets)
        row.addWidget(self.preview)
        row.addWidget(self.regenerate)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Project-approved Story"))
        layout.addWidget(self.story)
        layout.addLayout(row)
        layout.addWidget(self.summary)
        layout.addWidget(self.close_button)
        self.inspect.clicked.connect(self.discover)
        self.preview.clicked.connect(self.review_one)
        self.regenerate.clicked.connect(self.regenerate_one)
        self.close_button.clicked.connect(self.reject)
        self.preview.setEnabled(False)
        self.regenerate.setEnabled(False)

    def discover(self) -> None:
        self.assets.clear()
        try:
            candidates = self.review_service.discover()
        except (StoryBatchError, ValueError, OSError) as exc:
            QMessageBox.warning(self, "CAP Asset Discovery", str(exc))
            return
        lines = []
        for candidate in candidates:
            state = (
                "Already specified"
                if candidate.has_specification
                else "CAP Draft exists"
                if candidate.has_cap
                else "Missing CAP — will require explicit creation"
            )
            lines.append(f"{candidate.asset_id} — {candidate.name} ({candidate.category}): {state}")
            if not candidate.has_specification:
                self.assets.addItem(candidate.asset_id, candidate.asset_id)
        self.summary.setPlainText(
            "\n".join(lines) if lines else "No registered bound assets found in Shot ledger."
        )
        self.preview.setEnabled(self.assets.count() > 0 and self.story.count() > 0)
        self.regenerate.setEnabled(self.preview.isEnabled())

    def regenerate_one(self) -> None:
        choice = QMessageBox.question(
            self,
            "Regenerate CAP Proposal Using AI?",
            "This discards the cached proposal and makes new paid OpenAI requests. "
            "Existing CAP approvals are not changed. Proceed?",
        )
        if choice == QMessageBox.StandardButton.Yes:
            self.review_one(force_regenerate=True)

    def review_one(self, *, force_regenerate: bool = False) -> None:
        story_id = self.story.currentData()
        asset_id = self.assets.currentData()
        if not isinstance(story_id, str) or not isinstance(asset_id, str):
            return
        try:
            fingerprint = self.review_service.batch.current_story_fingerprint(story_id)
            asset = self.generator.assets.get(asset_id)
            asset_fingerprint = cache_fingerprint(
                asset.asset_id, asset.name, asset.category.value, asset.description
            )
            provider = self.generator.provider
            provider_fingerprint = cache_fingerprint(
                type(provider).__module__,
                type(provider).__qualname__,
                str(getattr(provider, "_model", "")),
                "cap-design-prompt-v2",
            )
            cache_key = (story_id, asset_id, fingerprint, asset_fingerprint, provider_fingerprint)
            eligible_assets = self.review_service.discover()
            if asset_id not in {
                item.asset_id for item in eligible_assets if not item.has_specification
            }:
                raise StoryBatchError("Asset is no longer eligible for a new CAP specification")
            cached = None if force_regenerate else self._proposal_cache.get(cache_key)
            if cached is None and not force_regenerate and self.cache is not None:
                cached = self.cache.load(
                    story_id, asset_id, fingerprint, asset_fingerprint, provider_fingerprint
                )
            if cached is not None:
                item = cached
            else:
                batch = self.review_service.batch.preview(story_id, (asset_id,))
                if not batch.candidates:
                    QMessageBox.warning(
                        self, "CAP Batch Review", "\n".join(batch.skipped) or "No eligible proposal"
                    )
                    return
                item = batch.candidates[0]
                if self.cache is not None:
                    self.cache.save(item, asset_fingerprint, provider_fingerprint)
            self._proposal_cache[cache_key] = item
            dialog = StoryCAPSpecificationDialog(item.proposal, self)
            if not dialog.exec():
                return
            detail_dialog = CAPDetailReviewDialog(
                dialog.reviewed(),
                suggestions=item.proposal.design_suggestions,
                quality_issues=item.proposal.quality_issues,
                parent=self,
            )
            if not detail_dialog.exec():
                return
            confirm = QMessageBox.question(
                self,
                "Create Reviewed Draft CAP?",
                f"Save the reviewed CAP specification for {asset_id}?\n"
                "A missing CAP record will be created in Draft status.\n"
                "No canon, reference, or production approval will be granted.",
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return
            self.review_service.save_reviewed(
                story_id, dialog.reviewed(), item.story_fingerprint, detail_dialog.reviewed()
            )
        except (StoryBatchError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, "CAP Batch Review", str(exc))
            return
        self._proposal_cache.clear()
        QMessageBox.information(self, "CAP Draft Saved", f"{asset_id} saved as Draft.")
        self.discover()
