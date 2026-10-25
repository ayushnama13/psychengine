"""Ingest CLI.

Usage:
  python -m psychengine.ingest.cli list                          # show pending books
  python -m psychengine.ingest.cli one <pdf_path>                # ingest one
  python -m psychengine.ingest.cli all [--yes]                   # ingest all under BOOKS_DIR
  python -m psychengine.ingest.cli stats                         # show DB stats
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from psychengine.config import BOOKS_DIR, DB_PATH, DEFAULT_CHUNK_TOKENS
from psychengine.db import connect, init
from psychengine.ingest.extract import extract_pages, book_summary
from psychengine.ingest.chunk import chunk_pages


CLUSTER_MAP = {
    "dark_psychology": "dark_psychology",
    "influence_persuasion": "dark_psychology",
    "seduction_dating": "social_dynamics",
    "mindset": "mindset",
    "psychology_theory": "psychology_theory",
}


def guess_metadata(pdf_path: Path):
    name = pdf_path.stem
    name = re.sub(r"^_?OceanofPDF\.com_", "", name, flags=re.IGNORECASE)
    name = re.sub(r"_?libgen\.li.*$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"_compressed$", "", name, flags=re.IGNORECASE)
    name = name.replace("_", " ").strip()

    author = ""
    # patterns like "Title by Author" or "Author - Title"
    m = re.search(r"\s+by\s+(.+?)(?:\s*-\s*libgen|\s*\(.*\)|\s*\[.*\]|$)", name, re.IGNORECASE)
    if m:
        author = m.group(1).strip()
        name = name[:m.start()].strip()
    else:
        m2 = re.match(r"^([A-Z][A-Za-z\.\, ]+?)\s+-\s+(.+)$", name)
        if m2:
            author = m2.group(1).strip()
            name = m2.group(2).strip()

    name = re.sub(r"\s*\[[^\]]*\]\s*", " ", name).strip()
    name = re.sub(r"\s+", " ", name)
    return name or pdf_path.stem, author


def cluster_for(pdf_path: Path) -> str:
    parts = pdf_path.relative_to(BOOKS_DIR).parts
    if parts:
        return CLUSTER_MAP.get(parts[0], parts[0])
    return "uncategorized"


def already_ingested(conn, file_path: str) -> bool:
    cur = conn.execute("SELECT 1 FROM books WHERE file_path = ?", (file_path,))
    return cur.fetchone() is not None


def ingest_one(pdf_path: Path, target_tokens: int = DEFAULT_CHUNK_TOKENS, verbose: bool = True) -> dict:
    conn = connect()
    file_str = str(pdf_path)
    if already_ingested(conn, file_str):
        if verbose:
            print(f"[skip] already ingested: {pdf_path.name}")
        conn.close()
        return {"status": "skipped", "path": file_str}

    title, author = guess_metadata(pdf_path)
    cluster = cluster_for(pdf_path)
    summary = book_summary(pdf_path)
    if not author and summary["author_meta"]:
        author = summary["author_meta"]

    if verbose:
        print(f"[ingest] {pdf_path.name}")
        print(f"  title:   {title}")
        print(f"  author:  {author or '<unknown>'}")
        print(f"  cluster: {cluster}")
        print(f"  pages:   {summary['page_count']}")

    pages = list(extract_pages(pdf_path))
    if not pages:
        if verbose:
            print(f"[warn] no extractable text in {pdf_path.name}")
        conn.close()
        return {"status": "no_text", "path": file_str}

    chunks = chunk_pages(pages, target_tokens=target_tokens)
    if not chunks:
        conn.close()
        return {"status": "no_chunks", "path": file_str}

    cur = conn.execute(
        "INSERT INTO books(title, author, cluster, file_path, total_chunks) VALUES(?,?,?,?,?)",
        (title, author, cluster, file_str, len(chunks)),
    )
    book_id = cur.lastrowid
    conn.executemany(
        "INSERT INTO chunks(book_id, chapter_name, chunk_index, text, page_start, page_end, token_estimate) "
        "VALUES(?,?,?,?,?,?,?)",
        [
            (book_id, c.chapter_name, c.chunk_index, c.text, c.page_start, c.page_end, c.token_estimate)
            for c in chunks
        ],
    )
    conn.commit()
    conn.close()
    if verbose:
        print(f"  -> {len(chunks)} chunks")
    return {"status": "ingested", "path": file_str, "chunks": len(chunks), "book_id": book_id}


def cmd_list(args):
    init()
    pdfs = sorted(BOOKS_DIR.rglob("*.pdf"))
    conn = connect()
    done = {row["file_path"] for row in conn.execute("SELECT file_path FROM books")}
    conn.close()
    pending = [p for p in pdfs if str(p) not in done]
    print(f"Total PDFs:     {len(pdfs)}")
    print(f"Already done:   {len(pdfs) - len(pending)}")
    print(f"Pending:        {len(pending)}\n")
    for p in pending[:50]:
        print(f"  - {p.relative_to(BOOKS_DIR)}")
    if len(pending) > 50:
        print(f"  ... +{len(pending) - 50} more")


def cmd_one(args):
    init()
    p = Path(args.path).resolve()
    if not p.exists():
        print(f"[err] not found: {p}")
        sys.exit(1)
    ingest_one(p)


def cmd_all(args):
    init()
    pdfs = sorted(BOOKS_DIR.rglob("*.pdf"))
    conn = connect()
    done = {row["file_path"] for row in conn.execute("SELECT file_path FROM books")}
    conn.close()
    pending = [p for p in pdfs if str(p) not in done]
    if not pending:
        print("[ok] nothing to ingest.")
        return
    print(f"\nAbout to ingest {len(pending)} PDFs ({sum(p.stat().st_size for p in pending)/1e6:.0f} MB).")
    print(f"DB: {DB_PATH}")
    if not args.yes:
        ans = input("Proceed? [y/N] ").strip().lower()
        if ans != "y":
            print("aborted.")
            return
    results = {"ingested": 0, "skipped": 0, "no_text": 0, "no_chunks": 0, "err": 0}
    for p in tqdm(pending, desc="ingesting"):
        try:
            r = ingest_one(p, verbose=False)
            results[r["status"]] = results.get(r["status"], 0) + 1
        except Exception as e:
            results["err"] += 1
            print(f"[err] {p.name}: {e}")
    print("\nDone:")
    for k, v in results.items():
        print(f"  {k}: {v}")


def cmd_stats(args):
    init()
    conn = connect()
    n_books = conn.execute("SELECT COUNT(*) c FROM books").fetchone()["c"]
    n_chunks = conn.execute("SELECT COUNT(*) c FROM chunks").fetchone()["c"]
    by_cluster = conn.execute(
        "SELECT cluster, COUNT(*) n_books, SUM(total_chunks) n_chunks FROM books GROUP BY cluster"
    ).fetchall()
    n_topics = conn.execute("SELECT COUNT(*) c FROM topics").fetchone()["c"]
    print(f"DB: {DB_PATH}")
    print(f"Books:  {n_books}")
    print(f"Chunks: {n_chunks}")
    print(f"Topics: {n_topics}")
    print("\nBy cluster:")
    for r in by_cluster:
        print(f"  {r['cluster']:20s} {r['n_books']:3d} books  {r['n_chunks'] or 0:6d} chunks")
    conn.close()


def main():
    p = argparse.ArgumentParser(prog="psychengine.ingest")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list").set_defaults(func=cmd_list)
    one = sub.add_parser("one"); one.add_argument("path"); one.set_defaults(func=cmd_one)
    a = sub.add_parser("all"); a.add_argument("--yes", action="store_true"); a.set_defaults(func=cmd_all)
    sub.add_parser("stats").set_defaults(func=cmd_stats)
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
