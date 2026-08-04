"""Tests for compiled prompt-package differencing."""

from __future__ import annotations

from dataclasses import replace

from vscs.application.prompt_graph import (
    PromptGraphChangeArea,
    PromptGraphChangeKind,
    PromptGraphDiffer,
    PromptPackage,
    PromptPackageProvenance,
    PromptSection,
    PromptSectionKind,
)
from vscs.application.prompt_graph.validation import (
    PromptGraphCompleteness,
    PromptGraphValidationReport,
)


def _package(*, continuity: str, references: tuple[str, ...]) -> PromptPackage:
    validation = PromptGraphValidationReport(
        "GRAPH-001",
        PromptGraphCompleteness(100, 100, 100, True),
    )
    provenance = PromptPackageProvenance(
        "GRAPH-001",
        "1.0",
        "a" * 64,
        "XORIX",
        "EP-001",
        "SCN-001",
        "SHT-001",
        None,
    )
    return PromptPackage(
        "GRAPH-001:prompt",
        (
            PromptSection(PromptSectionKind.VISUAL_INTENT, ()),
            PromptSection(PromptSectionKind.CONTINUITY, ()),
        ),
        f"Orbital approach. {continuity}",
        "No visual clutter.",
        ("CAP-SHP-IRON-HORIZON",),
        references,
        provenance,
        validation,
    )


def test_package_diff_reports_prompt_and_reference_changes() -> None:
    before = _package(
        continuity="Maintain orientation.",
        references=("REF-01",),
    )
    after = replace(
        _package(
            continuity="Maintain orientation and engine state.",
            references=("REF-01", "REF-02"),
        ),
        sections=(
            PromptSection(PromptSectionKind.VISUAL_INTENT, ()),
            PromptSection(PromptSectionKind.CONTINUITY, ()),
        ),
    )

    diff = PromptGraphDiffer().compare_packages(before, after)

    assert any(
        change.area is PromptGraphChangeArea.POSITIVE_PROMPT
        and change.kind is PromptGraphChangeKind.MODIFIED
        for change in diff.changes
    )
    assert any(
        change.area is PromptGraphChangeArea.REFERENCE
        and change.subject == "REF-02"
        and change.kind is PromptGraphChangeKind.ADDED
        for change in diff.changes
    )
