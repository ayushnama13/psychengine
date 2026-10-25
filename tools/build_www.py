"""Turn content.db into static JSON under www/content/ (what the app loads at runtime).

usage: build_www.py content.db [--www www]
  www/content/index.json                 books + chapters + version
  www/content/<book_uid>/<chapter_idx>.json   [{"u": uid, "t": text, "h": is_heading}, ...]
"""
import argparse
import json
import shutil
import sqlite3
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("db")
ap.add_argument("--www", default="www")
a = ap.parse_args()

root = Path(a.www) / "content"
shutil.rmtree(root, ignore_errors=True)
root.mkdir(parents=True)
db = sqlite3.connect(a.db)

books = []
for buid, title, author in db.execute("SELECT uid, title, author FROM books ORDER BY sort_idx"):
    chapters = []
    for cuid, idx, ctitle in db.execute(
            "SELECT uid, idx, title FROM chapters WHERE book_uid=? ORDER BY idx", (buid,)):
        paras = [{"u": u, "t": t, "h": h} for u, t, h in db.execute(
            "SELECT uid, text, is_heading FROM paragraphs WHERE chapter_uid=? ORDER BY idx", (cuid,))]
        (root / buid).mkdir(exist_ok=True)
        (root / buid / f"{idx}.json").write_text(json.dumps(paras, ensure_ascii=False, separators=(",", ":")))
        chapters.append({"uid": cuid, "idx": idx, "title": ctitle, "n": len(paras),
                         "chars": sum(len(p["t"]) for p in paras)})
    books.append({"uid": buid, "title": title, "author": author, "chapters": chapters})

version = db.execute("SELECT value FROM meta WHERE key='content_version'").fetchone()[0]
(root / "index.json").write_text(json.dumps({"version": version, "books": books}, ensure_ascii=False))
print(f"{len(books)} books -> {root} ({sum(len(b['chapters']) for b in books)} chapters)")
