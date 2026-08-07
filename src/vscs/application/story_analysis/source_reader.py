"""Source-text loading for the Story Analysis UI.

The reader deliberately uses only core VSCS dependencies. Text, Markdown,
Final Draft XML and DOCX files can be analysed locally. PDF ingestion remains a
separate document-import concern until a PDF parser is part of the runtime.
"""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from vscs.application.story import StoryRecord, StorySourceType


class StorySourceReadError(RuntimeError):
    """Raised when a configured story source cannot be converted to text."""


class StorySourceReader:
    """Load story source text without changing the configured source file."""

    def read(self, story: StoryRecord) -> str:
        path = self._path(story)
        try:
            if story.source_type is StorySourceType.DOCX or path.suffix.casefold() == ".docx":
                text = self._docx_text(path)
            elif story.source_type is StorySourceType.PDF or path.suffix.casefold() == ".pdf":
                raise StorySourceReadError(
                    "PDF story analysis is not available in Phase 18.2.5. "
                    "Use DOCX, Markdown, Final Draft or plain text for analysis."
                )
            elif story.source_type is StorySourceType.SCREENPLAY or path.suffix.casefold() == ".fdx":
                text = self._xml_text(path)
            else:
                text = path.read_text(encoding="utf-8-sig")
        except StorySourceReadError:
            raise
        except (OSError, UnicodeError, BadZipFile, ElementTree.ParseError) as exc:
            raise StorySourceReadError(f"Unable to read Story source: {exc}") from exc
        if not text.strip():
            raise StorySourceReadError("Story source contains no analysable text")
        return text

    @staticmethod
    def _path(story: StoryRecord) -> Path:
        if not story.source_path.strip():
            raise StorySourceReadError(
                "This Story has no source file. Edit the Story and select a source file first."
            )
        path = Path(story.source_path).expanduser()
        if not path.is_file():
            raise StorySourceReadError(f"Story source file does not exist: {path}")
        return path

    @staticmethod
    def _docx_text(path: Path) -> str:
        with ZipFile(path) as archive:
            document = archive.read("word/document.xml")
        root = ElementTree.fromstring(document)
        paragraphs: list[str] = []
        for paragraph in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"):
            text = "".join(
                node.text or ""
                for node in paragraph.iter(
                    "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"
                )
            )
            if text.strip():
                paragraphs.append(text)
        return "\n\n".join(paragraphs)

    @staticmethod
    def _xml_text(path: Path) -> str:
        root = ElementTree.parse(path).getroot()
        paragraphs: list[str] = []
        for element in root.iter():
            if element.tag.rsplit("}", 1)[-1] != "Paragraph":
                continue
            text = "".join(element.itertext()).strip()
            if text:
                paragraphs.append(text)
        return "\n\n".join(paragraphs)
