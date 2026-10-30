"""Batch Story CAP proposal review, with deliberate per-item persistence."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from vscs.application.caps.authoritative_shot_text import ShotTextAuthorityError
from vscs.application.caps.generator import CAPGeneratorService
from vscs.application.caps.governed_plan_adapter import GovernedProductionPlanAdapter
from vscs.application.caps.governed_planning_evidence import (
    ProductionPlanningContracts,
    discover_governed_shot_evidence,
    verified_governed_shot_evidence,
    verified_shots_to_spatial_sources,
)
from vscs.application.caps.proposal_cache import CAPProposalCache, cache_fingerprint
from vscs.application.caps.shot_spatial_evidence import ShotSpatialSource
from vscs.application.caps.spatial_acceptance import AcceptanceScenario, run_spatial_acceptance
from vscs.application.caps.spatial_graph import assess_spatial_graph
from vscs.application.caps.spatial_proposals import load_project_spatial_candidates
from vscs.application.caps.spatial_report import build_spatial_review_report
from vscs.application.caps.story_batch import (
    StoryBatchError,
    StoryBatchProposal,
    StoryCAPBatchService,
)
from vscs.application.caps.story_batch_review import StoryCAPBatchReviewService
from vscs.application.caps.story_scene_authority import StorySceneAuthority
from vscs.application.caps.story_specification import StoryCAPSpecificationService
from vscs.application.caps.structured_specification import CAPStructuredSpecificationService
from vscs.application.shots.service import ShotPlanningService
from vscs.application.story.lifecycle import StoryLifecycleService, StoryStatus
from vscs.application.story.service import StoryService
from vscs.presentation.dialogs.cap_detail_review_dialog import CAPDetailReviewDialog
from vscs.presentation.dialogs.spatial_continuity_report_dialog import (
    SpatialContinuityReportDialog,
)
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
        self.map_scenes = QPushButton("Assign Story Scenes (Reviewed)")
        self.preview = QPushButton("Review Cached Proposal")
        self.regenerate = QPushButton("Generate / Regenerate Using AI (Paid)")
        self.spatial_acceptance = QPushButton("Spatial Geometry Acceptance (Offline)")
        self.acceptance_scenario = QComboBox()
        for scenario in AcceptanceScenario:
            self.acceptance_scenario.addItem(scenario.value.replace("_", " ").title(), scenario)
        self.close_button = QPushButton("Close")
        self.summary = QTextEdit()
        self.summary.setReadOnly(True)
        self.summary.setPlainText(
            "Select an approved Story. Discovery reads only persisted Shot asset bindings. "
            "Review Cached Proposal never calls OpenAI. "
            "Generate / Regenerate Using AI (Paid) always requires a cost confirmation. "
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
        layout.addWidget(self.map_scenes)
        acceptance_row = QHBoxLayout()
        acceptance_row.addWidget(self.acceptance_scenario)
        acceptance_row.addWidget(self.spatial_acceptance)
        layout.addLayout(acceptance_row)
        layout.addWidget(self.summary)
        layout.addWidget(self.close_button)
        self.inspect.clicked.connect(self.discover)
        self.map_scenes.clicked.connect(self.assign_story_scenes)
        self.preview.clicked.connect(self.review_one)
        self.regenerate.clicked.connect(self.regenerate_one)
        self.close_button.clicked.connect(self.reject)
        self.spatial_acceptance.clicked.connect(self.review_spatial_acceptance)
        self.preview.setEnabled(False)
        self.regenerate.setEnabled(False)

    def review_spatial_acceptance(self) -> None:
        """Run isolated geometry test data; never query or write a project."""
        scenario = self.acceptance_scenario.currentData()
        if not isinstance(scenario, str):
            return
        result = run_spatial_acceptance(AcceptanceScenario(scenario))
        SpatialContinuityReportDialog(result.report, self).exec()

    def assign_story_scenes(self) -> None:
        """Explicit operator ownership assignment, never inferred from episode IDs."""
        story_id = self.story.currentData()
        root = self.generator.assets.projects.project_directory
        if not isinstance(story_id, str) or root is None:
            return
        try:
            fingerprint = self.review_service.batch.current_story_fingerprint(story_id)
            service = StoryService(self.generator.assets.projects)
            adapter = GovernedProductionPlanAdapter(
                root, service, ShotPlanningService(self.generator.assets.projects)
            )
            report = adapter.diagnostics()
            available = report.scene_ids
            if not available and (root / "planning" / "episode_plans.json").is_file():
                try:
                    governed = discover_governed_shot_evidence(root, story_id)
                    QMessageBox.information(
                        self,
                        "Governed Planning Authority Located",
                        "The active project uses planning/episode_plans.json, "
                        "scene_plans.json, shot_plans.json and asset_resolutions.json. "
                        f"Story-linked Shots found: {len(governed.candidates)}. "
                        "These are discovery-only until the original contract hash "
                        "verification implementation is connected. No duplicate "
                        "Scene or Shot records are needed. No CAP dependency was added.",
                    )
                    return
                except ShotTextAuthorityError as exc:
                    QMessageBox.warning(self, "Governed Planning Authority", str(exc))
                    return
            if not available:
                QMessageBox.information(
                    self,
                    "Story Scene Ownership",
                    f"No persisted Scenes in active project.\\n"
                    f"Scene source: {report.scene_source}\\n"
                    f"Shot source: {report.shot_source}\\n"
                    f"Persisted Shots: {report.shot_count}\\n"
                    "Story Workspace must show the same active project and sources. "
                    "No duplicate records will be created.",
                )
                return
            raw, accepted = QInputDialog.getText(
                self,
                "Explicit Story Scene Ownership",
                "Select Scene IDs separated by commas. Existing Scenes: " + ", ".join(available),
            )
            if not accepted:
                return
            ids = tuple(part.strip() for part in raw.split(",") if part.strip())
            if not ids:
                return
            if (
                QMessageBox.question(
                    self,
                    "Confirm Story Scene Authority",
                    f"Associate {', '.join(ids)} with approved {story_id}? "
                    "This saves a separate reviewed ownership ledger, not Story Canon.",
                )
                != QMessageBox.StandardButton.Yes
            ):
                return
            if fingerprint != self.review_service.batch.current_story_fingerprint(story_id):
                raise ShotTextAuthorityError("Story changed while assigning Scenes")
            StorySceneAuthority(root, service).assign(story_id, fingerprint, ids)
            QMessageBox.information(
                self, "Story Scene Authority", "Reviewed Story-to-Scene scope saved."
            )
        except (ShotTextAuthorityError, StoryBatchError, ValueError, OSError) as exc:
            QMessageBox.warning(self, "Story Scene Authority", str(exc))

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
            "Generate CAP Proposal Using AI (Paid)?",
            "This makes new paid OpenAI requests and replaces any cached proposal. "
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
            elif not force_regenerate:
                QMessageBox.information(
                    self,
                    "No Cached CAP Proposal",
                    "No valid cached proposal exists for this Story, asset and AI configuration. "
                    "Review Cached Proposal will not contact OpenAI. "
                    "Use Generate / Regenerate Using AI (Paid) to confirm a new paid request.",
                )
                return
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
            registered_ids = tuple(asset.asset_id for asset in self.generator.assets.list())
            spatial_candidates = load_project_spatial_candidates(
                self.review_service.batch.generator.specifications, registered_ids
            )
            story = self.stories.story(story_id)
            if story is None:
                raise StoryBatchError("Approved Story disappeared during spatial review")
            verified_shots: tuple[ShotSpatialSource, ...] = ()
            root = self.generator.assets.projects.project_directory
            governed_source = root is not None and (
                root / "planning" / "episode_plans.json"
            ).is_file()
            if root is not None:
                if governed_source:
                    try:
                        evidence = verified_governed_shot_evidence(
                            root, story_id, ProductionPlanningContracts()
                        )
                        verified_shots = verified_shots_to_spatial_sources(
                            evidence, selected_story_id=story_id
                        )
                    except (ShotTextAuthorityError, KeyError, TypeError, ValueError) as exc:
                        self.summary.setPlainText(
                            "Governed Shot evidence unavailable (no relationships inferred): "
                            + str(exc)
                        )
                else:
                    try:
                        adapter = GovernedProductionPlanAdapter(
                            root,
                            StoryService(self.generator.assets.projects),
                            ShotPlanningService(self.generator.assets.projects),
                        )
                        snapshot = adapter.verified_snapshot(
                            story_id, self.review_service.batch.current_story_fingerprint(story_id)
                        )
                        verified_shots = snapshot.shots
                    except ShotTextAuthorityError:
                        pass
            dialog = StoryCAPSpecificationDialog(
                item.proposal,
                self,
                spatial_candidates=spatial_candidates,
                story_evidence=(story_id, story.description, registered_ids),
                narrative_assets=tuple(self.generator.assets.list()),
                shot_sources=verified_shots,
            )
            if not dialog.exec():
                return
            if governed_source and root is not None and verified_shots:
                refreshed = verified_shots_to_spatial_sources(
                    verified_governed_shot_evidence(root, story_id, ProductionPlanningContracts()),
                    selected_story_id=story_id,
                )
                if refreshed != verified_shots:
                    raise StoryBatchError("Governed Shot evidence changed during CAP review")
            # Save the operator's reviewed fields as unapproved working material.
            # This is NOT CAP persistence, Canon approval or a provider call.
            item = replace(item, proposal=replace(item.proposal, specification=dialog.reviewed()))
            if self.cache is not None:
                self.cache.save(item, asset_fingerprint, provider_fingerprint)
            self._proposal_cache[cache_key] = item
            warnings = self.review_service.validate_reviewed_dependencies(dialog.reviewed())
            if dialog.reviewed().dependency_asset_ids:
                graph = assess_spatial_graph(
                    dialog.reviewed(), self.review_service.batch.generator.specifications
                )
                report = build_spatial_review_report(graph)
                SpatialContinuityReportDialog(report, self).exec()
            if warnings:
                self.summary.setPlainText(
                    "Dependency validation remains unverified:\n" + "\n".join(warnings)
                )
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
