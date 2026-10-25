"""PDF text extraction via PyMuPDF. Per-page output."""
from __future__ import annotations
from pathlib import Path
from typing import Iterator
import fitz  # type: ignore


class PageText:
    __slots__ = ("page_num", "text", "size_hint")

    def __init__(self, page_num: int, text: str, size_hint: float = 0.0):
        self.page_num = page_num
        self.text = text
        self.size_hint = size_hint


def extract_pages(pdf_path: Path) -> Iterator[PageText]:
    """Yield PageText per page. Skips blanks (<20 chars)."""
    doc = fitz.open(str(pdf_path))
    try:
        for i, page in enumerate(doc, start=1):
            txt = page.get_text("text") or ""
            txt = txt.strip()
            if len(txt) < 20:
                continue
            yield PageText(page_num=i, text=txt)
    finally:
        doc.close()


def book_summary(pdf_path: Path) -> dict:
    doc = fitz.open(str(pdf_path))
    try:
        meta = doc.metadata or {}
        return {
            "page_count": doc.page_count,
            "title_meta": meta.get("title") or "",
            "author_meta": meta.get("author") or "",
        }
    finally:
        doc.close()
