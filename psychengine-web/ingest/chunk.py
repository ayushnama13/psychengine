"""Chunk pages into chapter-aware blocks with fixed-size fallback.

Strategy:
1. Concatenate pages into one stream w/ page markers.
2. Detect chapter headers via regex (CHAPTER N, Chapter N: Title, all-caps lines).
3. Inside each chapter (or whole book if no chapters), split into ~target_tokens chunks
   on paragraph boundaries.
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Iterable, List

CHAPTER_PATTERNS = [
    re.compile(r"^\s*chapter\s+([0-9ivxlcdm]+)[\s:\.\-]*(.{0,80})?$", re.IGNORECASE),
    re.compile(r"^\s*part\s+([0-9ivxlcdm]+)[\s:\.\-]*(.{0,80})?$", re.IGNORECASE),
    re.compile(r"^\s*([0-9]{1,2})\.\s+([A-Z][A-Za-z0-9 ,'\-]{4,80})$"),
]
ALLCAPS_HEADER = re.compile(r"^\s*([A-Z][A-Z0-9 ,'\-]{6,80})\s*$")


def approx_tokens(text: str) -> int:
    # rough heuristic: 4 chars per token
    return max(1, len(text) // 4)


@dataclass
class Chunk:
    chapter_name: str
    chunk_index: int
    text: str
    page_start: int
    page_end: int

    @property
    def token_estimate(self) -> int:
        return approx_tokens(self.text)


def detect_chapter(line: str) -> str | None:
    line_s = line.strip()
    if not line_s or len(line_s) > 100:
        return None
    for pat in CHAPTER_PATTERNS:
        m = pat.match(line_s)
        if m:
            return line_s
    m = ALLCAPS_HEADER.match(line_s)
    if m and len(line_s.split()) <= 10:
        return line_s
    return None


def _split_paragraphs(text: str) -> List[str]:
    parts = re.split(r"\n\s*\n+", text)
    return [p.strip() for p in parts if p.strip()]


def chunk_pages(pages: Iterable, target_tokens: int = 1000) -> List[Chunk]:
    """pages: iterable of PageText. Returns list[Chunk]."""
    # build chapter-segmented stream
    sections: List[dict] = [{"chapter": "Front Matter", "paragraphs": [], "page_start": None, "page_end": None}]
    for p in pages:
        lines = p.text.split("\n")
        current_paragraph_buf: List[str] = []
        for ln in lines:
            ch = detect_chapter(ln)
            if ch:
                if current_paragraph_buf:
                    sections[-1]["paragraphs"].append((" ".join(current_paragraph_buf).strip(), p.page_num))
                    current_paragraph_buf = []
                sections.append({"chapter": ch, "paragraphs": [], "page_start": None, "page_end": None})
            else:
                current_paragraph_buf.append(ln)
        if current_paragraph_buf:
            sections[-1]["paragraphs"].append((" ".join(current_paragraph_buf).strip(), p.page_num))
        if sections[-1]["page_start"] is None:
            sections[-1]["page_start"] = p.page_num
        sections[-1]["page_end"] = p.page_num

    chunks: List[Chunk] = []
    chunk_index = 0
    for sec in sections:
        if not sec["paragraphs"]:
            continue
        # rebuild full section text as paragraphs joined by blank line, w/ page tracking
        buf_text: List[str] = []
        buf_tokens = 0
        buf_pstart: int | None = None
        buf_pend: int | None = None
        for para_text, pg in sec["paragraphs"]:
            para_text = re.sub(r"\s+", " ", para_text).strip()
            if not para_text:
                continue
            tk = approx_tokens(para_text)
            if buf_tokens + tk > target_tokens and buf_text:
                chunks.append(Chunk(
                    chapter_name=sec["chapter"],
                    chunk_index=chunk_index,
                    text="\n\n".join(buf_text),
                    page_start=buf_pstart or pg,
                    page_end=buf_pend or pg,
                ))
                chunk_index += 1
                buf_text, buf_tokens, buf_pstart, buf_pend = [], 0, None, None
            buf_text.append(para_text)
            buf_tokens += tk
            if buf_pstart is None:
                buf_pstart = pg
            buf_pend = pg
        if buf_text:
            chunks.append(Chunk(
                chapter_name=sec["chapter"],
                chunk_index=chunk_index,
                text="\n\n".join(buf_text),
                page_start=buf_pstart or sec["page_start"] or 1,
                page_end=buf_pend or sec["page_end"] or 1,
            ))
            chunk_index += 1
    return chunks
