"""Merge the topic catalog with each book's reviewed picks into the app's topics file.

usage: build_topics.py [--www www] [--topics tools/topics]
  reads  tools/topics/catalog.json            {"areas": [...], "topics": [{id, area, name, desc, q}]}
         tools/topics/books/<book_uid>.json   picks made with tools/topics_match.py
         www/content/index.json + www/content/<book_uid>/<idx>.json
  writes www/content/topics.json
    [{"id", "name", "desc", "area", "n", "books": {book_uid: count},
      "hits": [{"b": book_uid, "c": chapter_idx, "u": para_uid, "s": snippet, "x": note}, ...]}, ...]

Stdlib only: build.sh runs it with system python3. No embeddings or network here; the
picks were already chosen by a reviewer. A pick whose paragraph uid no longer exists (the
book was re-exported) is re-anchored by its stored text prefix; if that fails it is dropped
with a warning.
"""
import argparse
import json
import re
import sys
from pathlib import Path

SNIPPET = 240

ap = argparse.ArgumentParser()
ap.add_argument("--www", default="www")
ap.add_argument("--topics", default=str(Path(__file__).with_name("topics")))
a = ap.parse_args()

content = Path(a.www) / "content"
index = json.loads((content / "index.json").read_text())
catalog = json.loads((Path(a.topics) / "catalog.json").read_text())


def warn(msg):
    print(f"warning: {msg}", file=sys.stderr)


def snippet(text):
    """Opening of the paragraph, cut at a sentence end when one falls inside SNIPPET chars."""
    text = text.strip()
    if len(text) <= SNIPPET:
        return text
    ends = [m.end() for m in re.finditer(r"[.!?][\"'”’)]?(?=\s)", text[:SNIPPET + 1])]
    if ends and ends[-1] >= SNIPPET // 3:
        return text[:ends[-1]]
    return text[:SNIPPET].rsplit(" ", 1)[0] + "…"


hits_by_topic = {t["id"]: [] for t in catalog["topics"]}
for b in index["books"]:
    path = Path(a.topics) / "books" / f"{b['uid']}.json"
    if not path.exists():
        warn(f"{b['uid']} ({b['title'][:40]}) has no picks yet; run tools/topics_match.py on it")
        continue
    picks = json.loads(path.read_text())["picks"]
    paras = {}  # para uid -> (chapter idx, text)
    for c in b["chapters"]:
        for p in json.loads((content / b["uid"] / f"{c['idx']}.json").read_text()):
            paras[p["u"]] = (c["idx"], p["t"])
    seen = set()
    for tid, rows in picks.items():
        if tid not in hits_by_topic:
            warn(f"{b['uid']}: topic {tid} is not in the catalog; its {len(rows)} picks are skipped")
            continue
        for r in rows:
            u = r["u"]
            if u not in paras:
                u = next((k for k, (_, t) in paras.items() if t.startswith(r["p"])), None)
                if u is None:
                    warn(f"{b['uid']}: lost pick for {tid} ({r['p'][:40]!r})")
                    continue
            if (tid, u) in seen:
                continue
            seen.add((tid, u))
            c, t = paras[u]
            hit = {"b": b["uid"], "c": c, "u": u, "s": snippet(t)}
            if r.get("x"):
                hit["x"] = r["x"]
            hits_by_topic[tid].append(hit)

order = {b["uid"]: i for i, b in enumerate(index["books"])}
result = []
for t in catalog["topics"]:
    hits = hits_by_topic[t["id"]]
    if not hits:
        continue
    hits.sort(key=lambda h: (order[h["b"]], h["c"], h["u"]))  # reading order inside each book
    books = {}
    for h in hits:
        books[h["b"]] = books.get(h["b"], 0) + 1
    result.append({"id": t["id"], "name": t["name"], "desc": t["desc"], "area": t["area"],
                   "n": len(hits), "books": books, "hits": hits})

result.sort(key=lambda t: (-len(t["books"]), -t["n"]))  # cross-book topics first
(content / "topics.json").write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
print(f"{len(result)} topics, {sum(t['n'] for t in result)} passages -> {content / 'topics.json'}")
