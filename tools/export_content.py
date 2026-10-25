"""Build the read-only content.db bundled into the app, straight from the book PDFs.

usage: export_content.py --books 2,3,4 [--src psych.db] [--out app/assets/content.db]

The source DB is only used to look up book id -> title/author/pdf path.
UIDs are deterministic (sha1 of the PDF bytes + position) so user highlights
survive re-exports and books being added later.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import fitz

CHAPTERS = Path(__file__).resolve().parent / "chapters"  # optional per-book chapter title lists
DEFAULT_SRC = "/home/ayush/projects/psychengine/psychengine-web/db/psych.db"
SKIP_TITLE = re.compile(
    r"cover|title page|copyright|dedication|acknowledg|about the author|contents|"
    r"also by|index|bibliograph|permissions|^notes",
    re.I,
)
TERMINAL = tuple('.?!"”’)):')
ROMAN = re.compile(r"^[ivxlcdm]+$", re.I)


def file_uid(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()[:16]


def clean_block(text: str) -> str:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    out = ""
    for ln in lines:
        if out.endswith("-") and ln[:1].islower() and len(out) > 1 and out[-2].isalpha():
            out = out[:-1] + ln
        else:
            out = f"{out} {ln}" if out else ln
    return re.sub(r"\s+", " ", out).strip()


def split_long(text: str, limit: int = 1200, target: int = 700) -> list[str]:
    if len(text) <= limit:
        return [text]
    sentences = re.split(r"(?<=[.?!])\s+(?=[A-Z“\"‘'])", text)
    pieces, cur = [], ""
    for s in sentences:
        if cur and len(cur) + len(s) + 1 > target:
            pieces.append(cur)
            cur = s
        else:
            cur = f"{cur} {s}".strip()
    if cur:
        pieces.append(cur)
    return pieces


def is_heading(text: str) -> bool:
    return len(text) < 70 and not text.endswith((".", ",", ";")) and not text.isdigit()


def is_noise(text: str) -> bool:
    t = text.strip()
    return not t or t.isdigit() or bool(ROMAN.match(t))


def digitless(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\d+", "", text)).strip().lower()


def extract_paragraphs(doc: fitz.Document) -> list[tuple[int, str]]:
    """Return [(page_no_1based, paragraph_text)] with headers/footers removed."""
    pages = []
    zone_counts: Counter = Counter()
    for pno, page in enumerate(doc, start=1):
        h = page.rect.height
        blocks = []
        for b in sorted(page.get_text("blocks"), key=lambda b: (round(b[1]), b[0])):
            if b[6] != 0:
                continue
            text = clean_block(b[4])
            if is_noise(text):
                continue
            in_zone = b[3] < 0.10 * h or b[1] > 0.92 * h
            blocks.append((text, in_zone))
            if in_zone:
                zone_counts[digitless(text)] += 1
        pages.append((pno, blocks))

    paras: list[tuple[int, str]] = []
    for pno, blocks in pages:
        for text, in_zone in blocks:
            if in_zone and (len(text) < 80 or zone_counts[digitless(text)] >= 5):
                continue
            if zone_counts[digitless(text)] >= 5 and in_zone:
                continue
            if paras and not paras[-1][1].endswith(TERMINAL) and text[:1].islower():
                paras[-1] = (paras[-1][0], f"{paras[-1][1]} {text}")
            else:
                paras.append((pno, text))
    out = []
    for pno, text in paras:
        for piece in split_long(text):
            if len(piece) >= 2:
                out.append((pno, piece))
    return out


def toc_chapters(doc: fitz.Document) -> list[tuple[str, int]]:
    toc = [(lvl, t.strip(), p) for lvl, t, p in doc.get_toc() if lvl <= 2 and p >= 1]
    toc = [e for e in toc if not SKIP_TITLE.search(e[1])]
    if not toc:
        return []
    l2 = [e for i, e in enumerate(toc) if e[0] == 2]
    chosen = l2 if len(l2) >= 3 else [e for e in toc if e[0] == 1] or toc
    if len(chosen) >= 3 and len({p for _, _, p in chosen}) < len(chosen) / 2:
        return locate_titles(doc, [t for _, t, _ in chosen])  # broken bookmarks: all point at one page
    return [(t, p) for _, t, p in chosen]


def letters(text: str) -> str:
    text = re.sub(r"^\s*(chapter|part)\s+\w+\b", "", text, flags=re.I)
    return re.sub(r"[^a-z]", "", text.lower())


def locate_titles(doc: fitz.Document, titles: list[str]) -> list[tuple[str, int]]:
    """Find the page where each chapter title is printed as a heading, in order.

    Used when a PDF has no usable bookmarks. A page where three or more titles match is
    a printed contents page and is ignored. Titles that can't be found are dropped.
    """
    keys = [letters(t) for t in titles]
    pages = []
    for page in doc:
        blocks = [letters(b[4]) for b in page.get_text("blocks") if b[6] == 0]
        heads = [a + b for a, b in zip(blocks, blocks[1:] + [""])] + blocks
        pages.append([h for h in heads if h])
    hits = []
    for pno, heads in enumerate(pages, start=1):
        found = [i for i, k in enumerate(keys) if k and any(h.startswith(k) and len(h) <= len(k) + 30 for h in heads)]
        hits.append(found if len(found) < 3 else [])
    out, start = [], 0
    for i, t in enumerate(titles):
        pno = next((n for n in range(start, len(hits)) if i in hits[n]), None)
        if pno is None:
            print(f"  chapter not found: {t!r}", file=sys.stderr)
            continue
        out.append((t, pno + 1))
        start = pno
    return out


def heading_chapters(paras: list[tuple[int, str]]) -> list[tuple[str, int]]:
    """Fallback when the PDF has no bookmarks: 'Chapter N' / ALL-CAPS headings."""
    cand = []
    for i, (pno, text) in enumerate(paras):
        if re.match(r"^(CHAPTER|Chapter)\s+\w+", text) and len(text) < 80:
            cand.append((i, text))
        elif text.isupper() and 3 <= len(text) <= 60 and is_heading(text):
            cand.append((i, text))
    chosen, last = [], -1
    for i, text in cand:
        nxt = next((j for j, _ in cand if j > i), len(paras))
        body = sum(1 for _, t in paras[i + 1 : nxt] if not is_heading(t))
        if body >= 15 and i > last:
            chosen.append((text.title(), paras[i][0], i))
            last = i
    return chosen


def build_book(doc, paras, titles=None):
    """Return list of (chapter_title, [paragraph dicts]).

    titles: chapter titles from tools/chapters/<book_uid>.json, for PDFs without bookmarks.
    """
    chapters: list[tuple[str, list]] = []
    entries = locate_titles(doc, titles) if titles else toc_chapters(doc)
    if entries:
        entries.sort(key=lambda e: e[1])
        def chap_for(pno):
            title = "Front matter"
            for t, p in entries:
                if p <= pno:
                    title = t
                else:
                    break
            return title
        keys = [(chap_for(p), p, t) for p, t in paras]
    else:
        marks = heading_chapters(paras)
        starts = {m[2]: m[0] for m in marks}
        cur, keys = "Front matter", []
        for i, (p, t) in enumerate(paras):
            cur = starts.get(i, cur)
            keys.append((cur, p, t))
    for title, _, text in keys:
        if not chapters or chapters[-1][0] != title:
            chapters.append((title, []))
        chapters[-1][1].append(text)
    chapters = [c for c in chapters if c[1] and not SKIP_TITLE.search(c[0])]
    return [part for title, texts in chapters for part in split_chapter(title, texts)]


# Chapters longer than SPLIT_OVER chars are cut into parts of roughly MIN_PART..MAX_PART chars,
# preferably just before an internal sub-heading, otherwise at a paragraph boundary.
SPLIT_OVER, MIN_PART, MAX_PART, MIN_TAIL = 12000, 5000, 9000, 2500


STOP_END = {"the", "a", "an", "of", "and", "to", "in", "on", "for", "with", "by", "from", "at", "or", "is", "was"}
NOT_HEADING = re.compile(r"^(translated|by\b|edited|page\b|index|bibliograph|acknowledg|notes?\b|copyright)", re.I)


def clean_heading(t: str) -> bool:
    """A real sub-heading: short, capitalised, no attribution/year/dangling article, not a wrapped sentence."""
    words = t.split()
    return (is_heading(t) and 3 <= len(t) <= 60 and len(words) <= 9 and t[0].isupper()
            and not re.search(r"\b(1[0-9]|20)\d\d\b|\bpage \d+", t) and not NOT_HEADING.match(t)
            and words[-1].lower().rstrip(":") not in STOP_END and "," not in t
            and not (len(words) > 5 and sum(w[0].islower() for w in words) >= 3))


def heading_at(texts: list[str], i: int) -> bool:
    """texts[i] is a sub-heading followed by real body text."""
    return (clean_heading(texts[i]) and i + 1 < len(texts) and not is_heading(texts[i + 1])
            and len(texts[i + 1]) > 80)


def smart_title(t: str) -> str:
    small = {"a", "an", "the", "of", "and", "or", "to", "in", "on", "for", "at", "by", "with", "from"}
    words = []
    for i, w in enumerate(t.lower().split()):
        if re.fullmatch(r"[ivxl]+[:.,]?", w) and w not in ("i",):
            words.append(w.upper())
        elif i and w in small:
            words.append(w)
        else:
            words.append(re.sub(r"(^|[-—(])([a-zà-ÿ])", lambda m: m.group(1) + m.group(2).upper(), w))
    return " ".join(words)


def nice_title(t: str) -> str:
    return (smart_title(t) if t.isupper() else t).rstrip(":").strip()


def short_parent(title: str) -> str:
    m = re.match(r"^(LAW \d+)\b", title, re.I)
    if m:
        return m.group(1).title()
    t = nice_title(re.split(r"\s+[-–—]\s+", title)[0])
    return t if len(t) <= 40 else t[:40].rsplit(" ", 1)[0] + "…"


def split_chapter(title: str, texts: list[str]) -> list[tuple[str, list[str]]]:
    if sum(len(t) for t in texts) <= SPLIT_OVER:
        return [(title, texts)]
    parts: list[list[str]] = [[]]
    size = 0
    for i, t in enumerate(texts):
        head = heading_at(texts, i)
        if parts[-1] and ((head and size >= MIN_PART) or size >= MAX_PART):
            parts.append([])
            size = 0
        parts[-1].append(t)
        size += len(t)
    if len(parts) > 1 and sum(len(t) for t in parts[-1]) < MIN_TAIL:
        parts[-2].extend(parts.pop())
    if len(parts) == 1:
        return [(title, texts)]
    out = []
    for n, body in enumerate(parts, 1):
        sub = None
        if n > 1 and heading_at(body, 0):
            sub = nice_title(body[0])
            body = body[1:]  # the heading becomes the part title; don't print it twice
        base = title if n == 1 else short_parent(title)
        out.append((f"{base} · {sub}" if sub else f"{base} ({n}/{len(parts)})", body))
    return out


SCHEMA = """
CREATE TABLE books(uid TEXT PRIMARY KEY, title TEXT, author TEXT, sort_idx INTEGER);
CREATE TABLE chapters(uid TEXT PRIMARY KEY, book_uid TEXT, idx INTEGER, title TEXT);
CREATE TABLE paragraphs(uid TEXT PRIMARY KEY, chapter_uid TEXT, book_uid TEXT,
                        idx INTEGER, text TEXT, is_heading INTEGER DEFAULT 0);
CREATE INDEX idx_par_chapter ON paragraphs(chapter_uid, idx);
CREATE VIRTUAL TABLE paragraphs_fts USING fts5(text, content='paragraphs', tokenize='porter');
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=DEFAULT_SRC)
    ap.add_argument("--books", required=True)
    ap.add_argument("--out", default="app/assets/content.db")
    a = ap.parse_args()

    ids = [int(x) for x in a.books.split(",")]
    src = sqlite3.connect(f"file:{a.src}?mode=ro", uri=True)
    rows = {r[0]: r for r in src.execute(
        f"SELECT id, title, author, file_path FROM books WHERE id IN ({','.join('?' * len(ids))})", ids)}
    for i in ids:
        if i not in rows:
            print(f"error: book id {i} not in {a.src}", file=sys.stderr)
            return 1
        if not Path(rows[i][3]).exists():
            print(f"error: PDF missing: {rows[i][3]}", file=sys.stderr)
            return 1

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)
    db = sqlite3.connect(out)
    db.executescript(SCHEMA)

    for sort_idx, bid in enumerate(ids):
        _, title, author, path = rows[bid]
        buid = file_uid(Path(path))
        doc = fitz.open(path)
        override = CHAPTERS / f"{buid}.json"
        titles = json.loads(override.read_text()) if override.exists() else None
        chapters = build_book(doc, extract_paragraphs(doc), titles)
        db.execute("INSERT INTO books VALUES (?,?,?,?)", (buid, title.strip(), author or "", sort_idx))
        n_par = n_chr = 0
        for ci, (ctitle, texts) in enumerate(chapters):
            cuid = f"{buid}-c{ci:03d}"
            db.execute("INSERT INTO chapters VALUES (?,?,?,?)", (cuid, buid, ci, ctitle))
            for pi, text in enumerate(texts):
                db.execute(
                    "INSERT INTO paragraphs(uid,chapter_uid,book_uid,idx,text,is_heading) VALUES (?,?,?,?,?,?)",
                    (f"{cuid}-p{pi:04d}", cuid, buid, pi, text, int(is_heading(text))))
                n_par += 1
                n_chr += len(text)
        print(f"{title[:50]:50} chapters={len(chapters):3} paragraphs={n_par:5} chars={n_chr}")

    db.execute("INSERT INTO paragraphs_fts(paragraphs_fts) VALUES('rebuild')")
    db.executemany("INSERT INTO meta VALUES (?,?)", [
        ("schema_version", "1"),
        ("content_version", datetime.now(timezone.utc).isoformat(timespec="seconds"))])
    db.commit()
    db.execute("VACUUM")
    db.close()
    print(f"wrote {out} ({out.stat().st_size / 1e6:.2f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
