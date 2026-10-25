"""Embed book content with Gemini, one book at a time, cached on disk.

usage: emb.py [book_uid ...]        embed the given books (default: every book in www/content)
       emb.py --status              show what is cached

Run with the projects venv (needs numpy):  /home/ayush/projects/.venv/bin/python tools/emb.py
Keys come from $GOOGLE_AI_STUDIO_KEYS (comma/space separated); they are never printed.

Cache layout (data/emb/ is outside git and outside the backup hook):
  data/emb/<book_uid>/meta.json    {"model", "dims", "chunker", "chunks": [{"id","c","us","h"}]}
  data/emb/<book_uid>/vecs.npy     float16 [n_chunks, dims], L2-normalised
  data/emb/_topics/                same, for topic query texts (keyed by text hash)

A chunk is a run of consecutive body paragraphs inside one chapter, up to ~CHUNK_WORDS words.
Re-running on a re-exported book only embeds chunks whose text changed. A change of MODEL or
CHUNKER invalidates the cache instead of mixing incompatible vectors.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "www" / "content"
CACHE = ROOT / "data" / "emb"
MODEL = "models/gemini-embedding-2"
DIMS = 3072
CHUNKER = "v1-300w"
CHUNK_WORDS = 300
MIN_LEN = 160                      # shorter paragraphs only join a chunk, never start one alone
INDEX_LIKE = re.compile(r"\d+")    # index / notes pages are dense with page numbers
BATCH = 100
URL = "https://generativelanguage.googleapis.com/v1beta/{}:batchEmbedContents"


def keys():
    ks = [k for k in re.split(r"[,\s;]+", os.environ.get("GOOGLE_AI_STUDIO_KEYS", "")) if k]
    if not ks and os.environ.get("GEMINI_API_KEY"):
        ks = [os.environ["GEMINI_API_KEY"]]
    if not ks:
        sys.exit("no Gemini keys: set GOOGLE_AI_STUDIO_KEYS")
    return ks


class Embedder:
    """Round-robin over keys; a key that hits a rate limit rests for a minute."""

    def __init__(self):
        self.keys = keys()
        self.rest = [0.0] * len(self.keys)
        self.i = 0
        self.calls = 0

    def __call__(self, texts, task):
        body = json.dumps({"requests": [
            {"model": MODEL, "content": {"parts": [{"text": t}]}, "taskType": task} for t in texts]}).encode()
        for attempt in range(len(self.keys) * 4):
            k = self.i % len(self.keys)
            self.i += 1
            wait = self.rest[k] - time.time()
            if wait > 0:
                if all(r > time.time() for r in self.rest):
                    time.sleep(min(r for r in self.rest) - time.time())
                continue
            req = urllib.request.Request(URL.format(MODEL), data=body, headers={
                "x-goog-api-key": self.keys[k], "content-type": "application/json"})
            try:
                d = json.load(urllib.request.urlopen(req, timeout=120))
                self.calls += 1
                v = np.array([e["values"] for e in d["embeddings"]], dtype=np.float32)
                return v / np.linalg.norm(v, axis=1, keepdims=True)
            except urllib.error.HTTPError as e:
                msg = e.read()[:300].decode("utf8", "replace")
                if e.code in (429, 500, 503):
                    self.rest[k] = time.time() + 60
                    print(f"  key #{k}: HTTP {e.code}, resting it", file=sys.stderr)
                    continue
                sys.exit(f"embedding failed: HTTP {e.code} {msg}")
            except (urllib.error.URLError, TimeoutError) as e:
                print(f"  network: {e}; retrying", file=sys.stderr)
                time.sleep(5)
        sys.exit("embedding failed: every key is rate-limited; try again later")


def book_paras(b):
    for c in b["chapters"]:
        for p in json.loads((CONTENT / b["uid"] / f"{c['idx']}.json").read_text()):
            yield c["idx"], p


def chunks_of(b):
    """[{id, c, us: [para uids], text}] in reading order."""
    out, cur = [], None

    def flush():
        if cur and len(cur["text"]) >= MIN_LEN:
            out.append(cur)

    for cidx, p in book_paras(b):
        t = p["t"].strip()
        if p["h"] or len(INDEX_LIKE.findall(t)) >= 8:
            continue
        words = len(t.split())
        if cur and (cur["c"] != cidx or cur["w"] + words > CHUNK_WORDS):
            flush()
            cur = None
        if cur is None:
            cur = {"c": cidx, "us": [], "text": "", "w": 0}
        cur["us"].append(p["u"])
        cur["text"] = (cur["text"] + "\n" + t).strip()
        cur["w"] += words
    flush()
    for i, ch in enumerate(out):
        ch["id"] = i
        ch["h"] = hashlib.sha1(ch["text"].encode()).hexdigest()[:16]
        del ch["w"]
    return out


def load(dirname):
    """-> (meta, vecs float32) or (None, None). Rejects a cache from another model/chunker."""
    d = CACHE / dirname
    if not (d / "meta.json").exists():
        return None, None
    meta = json.loads((d / "meta.json").read_text())
    if meta.get("model") != MODEL or meta.get("dims") != DIMS or meta.get("chunker") != CHUNKER:
        return None, None
    return meta, np.load(d / "vecs.npy").astype(np.float32)


def save(dirname, meta, vecs):
    d = CACHE / dirname
    d.mkdir(parents=True, exist_ok=True)
    np.save(d / "vecs.npy", vecs.astype(np.float16))
    (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False))


def embed_texts(items, dirname, task, emb):
    """items: [{"h", ...}] with a "text" field. Reuses cached vectors by hash; returns (meta, vecs)."""
    old_meta, old_vecs = load(dirname)
    have = {}
    if old_meta:
        for row, v in zip(old_meta["chunks"], old_vecs):
            have[row["h"]] = v
    todo = [it for it in items if it["h"] not in have]
    for s in range(0, len(todo), BATCH):
        part = todo[s:s + BATCH]
        for it, v in zip(part, emb([it["text"] for it in part], task)):
            have[it["h"]] = v
        print(f"  {dirname}: {min(s + BATCH, len(todo))}/{len(todo)} embedded", file=sys.stderr)
    vecs = np.stack([have[it["h"]] for it in items]) if items else np.zeros((0, DIMS), np.float32)
    meta = {"model": MODEL, "dims": DIMS, "chunker": CHUNKER,
            "chunks": [{k: v for k, v in it.items() if k != "text"} for it in items]}
    save(dirname, meta, vecs)
    return meta, vecs, len(todo)


def index():
    return json.loads((CONTENT / "index.json").read_text())


def embed_book(b, emb):
    chs = chunks_of(b)
    meta, vecs, n_new = embed_texts(chs, b["uid"], "RETRIEVAL_DOCUMENT", emb)
    return len(chs), n_new


def topic_text(t):
    return f"{t['name']}. {t['q']}"


def topic_vecs(catalog, emb=None):
    """Vectors for every catalog topic (embedding only new or changed topic texts)."""
    items = [{"id": t["id"], "h": hashlib.sha1(topic_text(t).encode()).hexdigest()[:16], "text": topic_text(t)}
             for t in catalog]
    meta, vecs = load("_topics")
    have = {r["h"]: v for r, v in zip(meta["chunks"], vecs)} if meta else {}
    if all(it["h"] in have for it in items):
        return np.stack([have[it["h"]] for it in items])
    meta, vecs, _ = embed_texts(items, "_topics", "RETRIEVAL_QUERY", emb or Embedder())
    return vecs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("books", nargs="*")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    idx = index()
    if a.status:
        for b in idx["books"]:
            meta, vecs = load(b["uid"])
            print(f"{b['uid']:<40} {'%d chunks' % len(vecs) if meta else 'not embedded'}")
        return
    want = a.books or [b["uid"] for b in idx["books"]]
    by = {b["uid"]: b for b in idx["books"]}
    missing = [u for u in want if u not in by]
    if missing:
        sys.exit(f"unknown book uid(s): {', '.join(missing)}")
    emb = Embedder()
    t0 = time.time()
    for u in want:
        n, n_new = embed_book(by[u], emb)
        print(f"{u}: {n} chunks, {n_new} newly embedded")
    print(f"{emb.calls} API calls, {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
