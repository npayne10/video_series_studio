"""Phase 20.19.3B.2 source-document preview is advisory and non-mutating."""

from unittest.mock import Mock
from zipfile import ZipFile

import pytest

from vscs.application.caps.document_import import (
    CAPDocumentImportError,
    CAPDocumentImportService,
    preview_cap_docx,
)
from vscs.application.caps.structured_specification import CAPSpecificationError
from vscs.domain.assets.models import AssetCategory


def _docx(tmp_path, text):
    path = tmp_path / "source.docx"
    ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    paragraphs = "".join(f'<w:p><w:r><w:t>{line}</w:t></w:r></w:p>' for line in text)
    with ZipFile(path, "w") as archive:
        archive.writestr(
            "word/document.xml",
            f'<w:document xmlns:w="{ns}"><w:body>{paragraphs}</w:body></w:document>',
        )
    return path


def test_location_and_character_preview_preserves_document_provenance(tmp_path):
    source = _docx(
        tmp_path,
        [
            "CAP-LOC-001 v1.0",
            "Creation Asset Prompt",
            "The Apartment",
            "Visual Design Intent (LOCKED)",
            "Quiet, orderly architecture",
            "Architectural Identity (LOCKED)",
            "Layout",
            "Panoramic window opposite the bed",
            "Variables",
            "Time of day",
            "Morning",
            "Master Creation Prompt",
            "Wide studio reference of the apartment",
            "Dependencies",
            "CAP-CHR-001",
            "Continuity Rules",
            "Window and bed orientation unchanged",
            "Revision History",
            "Initial release",
            "CAP-CHR-001 v1.0",
            "Creation Asset Prompt",
            "Commander",
            "Visual Design Intent (LOCKED)",
            "Calm leader",
            "Identity (LOCKED)",
            "Face",
            "Defined jaw",
            "Master Creation Prompt",
            "Full body studio reference of commander",
            "Revision History",
            "Initial release",
        ],
    )
    proposals = preview_cap_docx(source)
    assert len(proposals) == 2
    location, character = proposals
    assert location.category == AssetCategory.LOCATION
    assert character.category == AssetCategory.CHARACTER
    assert location.name == "The Apartment"
    assert location.sections["location_identity"].startswith("Layout")
    assert "CAP-CHR-001" in location.sections["dependencies"]
    assert location.source_sha256 == character.source_sha256
    assert len(location.source_sha256) == 64
    assert "Initial release" not in character.sections["master_prompt"]


def test_source_identity_mismatch_is_blocked(tmp_path):
    proposal = preview_cap_docx(
        _docx(
            tmp_path,
            [
                "CAP-LOC-001 v1.0",
                "Visual Design Intent (LOCKED)",
                "Permanent room",
                "Master Creation Prompt",
                "Wide room reference",
            ],
        )
    )[0]
    with pytest.raises(CAPDocumentImportError, match="remapping"):
        proposal.to_draft_specification(
            target_asset_id="CAP-LOC-002",
            attributes={"layout": "Fixed"},
        )


def test_import_requires_human_mapping_and_an_empty_slot(tmp_path):
    proposal = preview_cap_docx(
        _docx(
            tmp_path,
            [
                "CAP-LOC-001 v1.0",
                "Visual Design Intent (LOCKED)",
                "Permanent room",
                "Master Creation Prompt",
                "Wide room reference",
            ],
        )
    )[0]
    specifications = Mock()
    specifications.get.return_value = None
    service = CAPDocumentImportService(specifications)
    with pytest.raises(CAPSpecificationError, match="category-specific"):
        service.apply_reviewed(proposal, target_asset_id="CAP-LOC-001", attributes={"hair": "brown"})
    specifications.save_draft.assert_not_called()

    saved = service.apply_reviewed(
        proposal, target_asset_id="CAP-LOC-001", attributes={"layout": "Fixed"}
    )
    assert saved.source_document_sha256 == proposal.source_sha256
    specifications.save_draft.assert_called_once()
    specifications.get.return_value = saved
    with pytest.raises(CAPSpecificationError, match="revision review"):
        service.apply_reviewed(
            proposal, target_asset_id="CAP-LOC-001", attributes={"layout": "Fixed"}
        )


def test_reject_invalid_docx_and_documents_without_cap_heading(tmp_path):
    path = tmp_path / "bad.docx"
    path.write_bytes(b"not a docx")
    with pytest.raises(CAPDocumentImportError):
        preview_cap_docx(path)
    with pytest.raises(CAPDocumentImportError, match="No recognized"):
        preview_cap_docx(_docx(tmp_path, ["No CAP here"]))
