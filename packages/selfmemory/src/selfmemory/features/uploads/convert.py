"""Turning uploads into something the agent can read.

Office documents and PDFs are converted to markdown with ``markitdown``; text
files are stored as they are; images and anything unconvertible are kept as
originals under ``assets/`` with a small markdown stub that points at them, so
an agent with vision can still open the image. Nothing is ever refused: a
source the server cannot read is still a source.

Converted output keeps the original extension in its name (``deck.pptx.md``)
so two uploads that differ only by type never collide.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import yaml

from selfmemory.features.wiki.adapters.files import IMAGE_EXTENSIONS, looks_binary

__all__ = ["Converted", "convert_file", "CONVERTIBLE"]

logger = logging.getLogger(__name__)

CONVERTIBLE = {
    ".pdf",
    ".docx",
    ".pptx",
    ".xlsx",
    ".xls",
    ".html",
    ".htm",
    ".epub",
    ".ipynb",
}


@dataclass(frozen=True)
class Converted:
    """The result of converting one upload.

    ``name`` is what to store in the scope's raw directory. ``content`` is its
    bytes. ``asset`` is set when the original must also be kept, under
    ``assets/<asset>``.
    """

    name: str
    content: bytes
    converted_by: str
    asset: str | None = None


def _frontmatter(title: str, original: str, converted_by: str) -> str:
    meta = {"title": title, "original": original, "converted_by": converted_by}
    return "---\n" + yaml.safe_dump(meta, sort_keys=False).strip() + "\n---\n\n"


def _markitdown(path: Path) -> str | None:
    try:
        from markitdown import MarkItDown
    except ImportError:  # pragma: no cover - optional dependency missing
        return None
    try:
        result = MarkItDown(enable_plugins=False).convert(str(path))
    except Exception as e:  # noqa: BLE001 - any converter failure means "keep original"
        logger.info("conversion failed for %s: %s", path.suffix, type(e).__name__)
        return None
    text = (result.text_content or "").strip()
    return text or None


def convert_file(original_name: str, staged: Path) -> Converted:
    stem = Path(original_name).stem or "upload"
    ext = Path(original_name).suffix.lower()

    if ext in CONVERTIBLE:
        text = _markitdown(staged)
        if text:
            body = _frontmatter(stem, original_name, "markitdown") + text + "\n"
            return Converted(f"{original_name}.md", body.encode("utf-8"), "markitdown")

    data = staged.read_bytes()
    if ext not in IMAGE_EXTENSIONS and not looks_binary(data):
        return Converted(original_name, data, "none")

    if ext in IMAGE_EXTENSIONS:
        body = (
            _frontmatter(stem, original_name, "none")
            + f"![{stem} — not yet described; run a vision ingest pass]"
            f"(assets/{original_name})\n"
        )
    else:
        body = (
            _frontmatter(stem, original_name, "none")
            + f"The original file is kept at `assets/{original_name}`; "
            "its contents could not be extracted as text.\n"
        )
    return Converted(
        f"{original_name}.md", body.encode("utf-8"), "none", asset=original_name
    )
