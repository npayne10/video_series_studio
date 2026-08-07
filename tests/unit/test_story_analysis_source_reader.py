"""Unit coverage for Phase 18.2.5 Story source loading."""

from __future__ import annotations

from zipfile import ZipFile

import pytest

from vscs.application.story import StoryRecord, StorySourceType
from vscs.application.story_analysis import StorySourceReader, StorySourceReadError


def _story(path: str, source_type: StorySourceType) -> StoryRecord:
    return StoryRecord(
        story_id="STORY-001",
        title="Xorix Trailer",
        source_type=source_type,
        source_path=path,
    )


def test_reader_loads_plain_text_without_modifying_source(tmp_path) -> None:
    path = tmp_path / "trailer.txt"
    path.write_text("# Arrival\n\nCommander James Spence watched Xorix.", encoding="utf-8")

    text = StorySourceReader().read(_story(str(path), StorySourceType.PLAIN_TEXT))

    assert "Commander James Spence" in text
    assert path.read_text(encoding="utf-8") == text


def test_reader_extracts_docx_paragraph_text(tmp_path) -> None:
    path = tmp_path / "trailer.docx"
    document_xml = """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>Arrival</w:t></w:r></w:p>
    <w:p><w:r><w:t>Commander James Spence watched Xorix.</w:t></w:r></w:p>
  </w:body>
</w:document>
"""
    with ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document_xml)

    text = StorySourceReader().read(_story(str(path), StorySourceType.DOCX))

    assert text == "Arrival\n\nCommander James Spence watched Xorix."


def test_reader_rejects_pdf_until_pdf_ingestion_is_available(tmp_path) -> None:
    path = tmp_path / "trailer.pdf"
    path.write_bytes(b"%PDF-1.7")

    with pytest.raises(StorySourceReadError, match="PDF story analysis is not available"):
        StorySourceReader().read(_story(str(path), StorySourceType.PDF))


def test_reader_requires_existing_source_file(tmp_path) -> None:
    missing = tmp_path / "missing.txt"

    with pytest.raises(StorySourceReadError, match="does not exist"):
        StorySourceReader().read(_story(str(missing), StorySourceType.PLAIN_TEXT))
