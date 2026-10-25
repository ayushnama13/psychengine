"""Review tools for topic passages: Gemini embeddings find candidates, a reviewer picks.

Run with the projects venv:  /home/ayush/projects/.venv/bin/python tools/topics_match.py <cmd> ...

  scan <book>                    how strongly each catalog topic shows up in a book
  cand <book> <topic> [-k 8]     best-matching chunks of one book for one topic
  discover <book> [-n 6]         groups of chunks that fit no catalog topic (new-topic ideas)
  backfill <topic> [-k 8]        cand for every embedded book that has not reviewed <topic> yet
  sheet <book> [-k 4] [--min .5] compact candidates for every topic <book> has not reviewed yet
  pick <book> < picks.json       save picks: {"<topic>": [[chunk_id, para_no, "note"], ...], ...}
                                 para_no = which paragraph of the chunk to open (0 = first).
                                 An empty list records "reviewed, nothing worth showing";
                                 --close records that for every topic not in the input.

Picks live in tools/topics/books/<book_uid>.json and are never rewritten for other books.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

import emb

TOPICS = Path(__file__).resolve().parent / "topics"
CATALOG = TOPICS / "catalog.json"
PREVIEW = 420


def catalog():
    return json.loads(CATALOG.read_text())["topics"]


def books():
    return {b["uid"]: b for b in emb.index()["books"]}


def book_vecs(uid):
    meta, vecs = emb.load(uid)
    if meta is None:
        sys.exit(f"{uid}: not embedded yet (run tools/emb.py {uid})")
    return meta["chunks"], vecs


def para_texts(b):
    return {p["u"]: p["t"] for _, p in emb.book_paras(b)}


def chapter_titles(b):
    return {c["idx"]: c["title"] for c in b["chapters"]}


def picks_path(uid):
    return TOPICS / "books" / f"{uid}.json"


def load_picks(uid):
    p = picks_path(uid)
    return json.loads(p.read_text()) if p.exists() else {"book": uid, "reviewed": [], "picks": {}}


def show(b, chunk, score, texts, titles):
    print(f"  [{chunk['id']}] {score:.3f}  ch{chunk['c']} {titles.get(chunk['c'], '')[:50]}")
    left = PREVIEW
    for i, u in enumerate(chunk["us"]):
        if left <= 0:
            print(f"     ({len(chunk['us']) - i} more paragraphs)")
            break
        t = texts[u]
        cut = t[:min(left, 200 if len(chunk["us"]) > 1 else left)]
        print(f"     p{i}: {cut}{'…' if len(cut) < len(t) else ''}")
        left -= len(cut)


def ranked(chunks, sims, k, per_chapter=2):
    out, per = [], {}
    for i in np.argsort(-sims):
        c = chunks[i]["c"]
        if per.get(c, 0) >= per_chapter:
            continue
        per[c] = per.get(c, 0) + 1
        out.append(i)
        if len(out) >= k:
            break
    return out


def cmd_scan(a):
    b = books()[a.book]
    chunks, vecs = book_vecs(a.book)
    cat = catalog()
    sims = vecs @ emb.topic_vecs(cat).T
    rows = sorted(((sims[:, j].max(), np.sort(sims[:, j])[-5:].mean(), t["id"]) for j, t in enumerate(cat)), reverse=True)
    print(f"{b['title'][:50]}: {len(chunks)} chunks")
    for top, top5, tid in rows:
        print(f"  {tid:<18} top {top:.3f}  top5 {top5:.3f}")


def cmd_cand(a, book=None, topic=None):
    uid, tid = book or a.book, topic or a.topic
    b = books()[uid]
    cat = catalog()
    j = next((i for i, t in enumerate(cat) if t["id"] == tid), None)
    if j is None:
        sys.exit(f"unknown topic {tid}")
    chunks, vecs = book_vecs(uid)
    sims = vecs @ emb.topic_vecs(cat)[j]
    texts, titles = para_texts(b), chapter_titles(b)
    print(f"== {cat[j]['name']} in {b['title'][:50]}")
    for i in ranked(chunks, sims, a.k):
        show(b, chunks[i], sims[i], texts, titles)


def kmeans(x, n, iters=30, seed=0):
    rng = np.random.default_rng(seed)
    cent = x[rng.choice(len(x), n, replace=False)]
    for _ in range(iters):
        lab = np.argmax(x @ cent.T, axis=1)
        for k in range(n):
            m = x[lab == k]
            if len(m):
                c = m.mean(0)
                cent[k] = c / np.linalg.norm(c)
    return lab, cent


def cmd_discover(a):
    b = books()[a.book]
    chunks, vecs = book_vecs(a.book)
    best = (vecs @ emb.topic_vecs(catalog()).T).max(1)
    loose = np.where(best < np.quantile(best, a.quantile))[0]
    lab, cent = kmeans(vecs[loose], a.n)
    texts, titles = para_texts(b), chapter_titles(b)
    print(f"{len(loose)} of {len(chunks)} chunks fit no topic well; {a.n} groups:")
    for k in np.argsort(-np.bincount(lab, minlength=a.n)):
        mem = loose[lab == k]
        if not len(mem):
            continue
        chs = sorted({chunks[i]["c"] for i in mem})
        print(f"\n-- group {k}: {len(mem)} chunks, chapters: {', '.join(titles[c][:30] for c in chs[:6])}")
        for i in mem[np.argsort(-(vecs[mem] @ cent[k]))][:3]:
            show(b, chunks[i], float(vecs[i] @ cent[k]), texts, titles)


def cmd_backfill(a):
    for uid in books():
        if emb.load(uid)[0] is None:
            continue
        if a.topic not in load_picks(uid)["reviewed"]:
            cmd_cand(a, uid, a.topic)


def cmd_sheet(a):
    """One compact review sheet per book: every unreviewed topic that shows up strongly enough."""
    b = books()[a.book]
    chunks, vecs = book_vecs(a.book)
    cat = catalog()
    done = set(load_picks(a.book)["reviewed"])
    sims = vecs @ emb.topic_vecs(cat).T
    texts, titles = para_texts(b), chapter_titles(b)
    weak = []
    print(f"# {b['title'][:60]} ({a.book}): {len(chunks)} chunks")
    for j, t in enumerate(cat):
        if t["id"] in done:
            continue
        if sims[:, j].max() < a.min:
            weak.append(t["id"])
            continue
        print(f"\n== {t['id']}: {t['name']}")
        for i in ranked(chunks, sims[:, j], a.k, per_chapter=1):
            if sims[i, j] < a.min:
                break
            ch = chunks[i]
            paras = " | ".join(f"p{n}: {texts[u][:a.width]}" for n, u in enumerate(ch["us"][:3]))
            print(f"[{ch['id']}] {sims[i, j]:.2f} {titles.get(ch['c'], '')[:30]} :: {paras}")
    print(f"\nweak (max < {a.min}): {' '.join(weak)}")


def cmd_pick(a):
    b = books()[a.book]
    chunks, _ = book_vecs(a.book)
    by_id = {c["id"]: c for c in chunks}
    texts = para_texts(b)
    ids = {t["id"] for t in catalog()}
    data = load_picks(a.book)
    data["title"] = b["title"]
    for tid, rows in json.load(sys.stdin).items():
        if tid not in ids:
            sys.exit(f"unknown topic {tid}")
        out = []
        for cid, pno, note in rows:
            ch = by_id[cid]
            u = ch["us"][min(pno, len(ch["us"]) - 1)]
            out.append({"c": ch["c"], "u": u, "p": texts[u][:80], "x": note})
        if out:
            data["picks"][tid] = out
        else:
            data["picks"].pop(tid, None)
        if tid not in data["reviewed"]:
            data["reviewed"].append(tid)
    if a.close:  # everything else on the sheet was weak or not worth showing
        data["reviewed"] += [t for t in sorted(ids) if t not in data["reviewed"]]
    picks_path(a.book).parent.mkdir(parents=True, exist_ok=True)
    picks_path(a.book).write_text(json.dumps(data, ensure_ascii=False, indent=1))
    print(f"{a.book}: {sum(len(v) for v in data['picks'].values())} picks over {len(data['picks'])} topics, "
          f"{len(data['reviewed'])} topics reviewed")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan"); s.add_argument("book"); s.set_defaults(f=cmd_scan)
    s = sub.add_parser("cand"); s.add_argument("book"); s.add_argument("topic"); s.add_argument("-k", type=int, default=8); s.set_defaults(f=cmd_cand)
    s = sub.add_parser("discover"); s.add_argument("book"); s.add_argument("-n", type=int, default=6)
    s.add_argument("--quantile", type=float, default=0.3); s.set_defaults(f=cmd_discover)
    s = sub.add_parser("backfill"); s.add_argument("topic"); s.add_argument("-k", type=int, default=8); s.set_defaults(f=cmd_backfill)
    s = sub.add_parser("sheet"); s.add_argument("book"); s.add_argument("-k", type=int, default=4)
    s.add_argument("--min", type=float, default=0.5); s.add_argument("--width", type=int, default=160); s.set_defaults(f=cmd_sheet)
    s = sub.add_parser("pick"); s.add_argument("book")
    s.add_argument("--close", action="store_true", help="mark every other topic reviewed with no picks"); s.set_defaults(f=cmd_pick)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
