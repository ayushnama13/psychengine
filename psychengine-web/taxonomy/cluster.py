"""Cluster raw concepts → topic groups.

Two passes:
1. Lexical normalization + alias merging (cheap, deterministic)
2. AI semantic clustering on the deduped list
"""
from __future__ import annotations
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from psychengine.db import connect
from psychengine.ai.router import chat, parse_json


STOPWORDS = {"the", "a", "an", "of", "and", "to", "in", "for"}


def normalize(c: str) -> str:
    c = c.lower().strip()
    c = re.sub(r"[\"\'\(\)\[\]]", "", c)
    c = re.sub(r"\s+", " ", c)
    toks = [t for t in c.split() if t not in STOPWORDS]
    return " ".join(toks).strip()


def collect_concepts() -> Counter:
    conn = connect()
    rows = conn.execute("SELECT raw_concepts FROM concept_extraction_log").fetchall()
    conn.close()
    counter: Counter = Counter()
    for r in rows:
        try:
            arr = json.loads(r["raw_concepts"])
        except Exception:
            continue
        for c in arr:
            n = normalize(c)
            if 3 <= len(n) <= 60:
                counter[n] += 1
    return counter


def lexical_dedupe(counter: Counter, min_count: int = 2) -> list[tuple[str, int]]:
    items = [(k, v) for k, v in counter.items() if v >= min_count]
    items.sort(key=lambda x: -x[1])
    return items


SYSTEM = """You are an expert in psychology, persuasion, and social dynamics taxonomy.
You receive a list of raw concept mentions extracted from books. Cluster them into coherent topics.
Each topic must aggregate semantically related concepts (e.g., "social proof", "herd mentality", "bandwagon effect" → one topic).

Output strict JSON:
{"topics": [
  {"name": "Topic Name (Title Case, 2-5 words)",
   "description": "1-2 sentence definition",
   "cluster_hint": "dark_psychology|social_dynamics|psychology_theory|mindset",
   "members": ["raw concept 1", "raw concept 2", ...]
  }, ...
]}

Rules:
- Aim for 25-40 topics total
- Every input concept MUST appear in exactly one topic's "members"
- Use canonical psychology/persuasion terminology for topic names
- Keep topic granularity practical: not too narrow (each concept is its own topic) and not too broad (everything in one bucket)
"""


def ai_cluster(items: list[tuple[str, int]], batch_size: int = 300) -> list[dict]:
    """Cluster items. If too many, run in batches and merge."""
    if not items:
        return []
    concept_list = [k for k, _ in items]
    all_topics: list[dict] = []
    for i in range(0, len(concept_list), batch_size):
        batch = concept_list[i : i + batch_size]
        user = f"Concept list ({len(batch)} items):\n" + "\n".join(f"- {c}" for c in batch) + "\n\nReturn JSON."
        resp, _ = chat(
            feature="topic_cluster",
            system=SYSTEM,
            user=user,
            json_mode=True,
            temperature=0.2,
            max_tokens=4096,
        )
        data = parse_json(resp)
        if isinstance(data, dict) and isinstance(data.get("topics"), list):
            all_topics.extend(data["topics"])
    # merge duplicate topic names across batches
    by_name: dict[str, dict] = {}
    for t in all_topics:
        name = (t.get("name") or "").strip()
        if not name:
            continue
        if name not in by_name:
            by_name[name] = {
                "name": name,
                "description": t.get("description", ""),
                "cluster_hint": t.get("cluster_hint", ""),
                "members": list(t.get("members") or []),
            }
        else:
            by_name[name]["members"].extend(t.get("members") or [])
    return list(by_name.values())


def run(min_count: int = 2):
    counter = collect_concepts()
    print(f"raw concept mentions: {sum(counter.values())}")
    print(f"unique concepts:      {len(counter)}")
    items = lexical_dedupe(counter, min_count=min_count)
    print(f"after dedupe (min_count={min_count}): {len(items)}")
    if not items:
        print("no concepts. run concept extraction first.")
        return
    topics = ai_cluster(items)
    print(f"clustered into {len(topics)} topics")
    # write to DB as unreviewed proposals; build member→topic map
    conn = connect()
    member_to_topic: dict[str, int] = {}
    for t in topics:
        cur = conn.execute(
            "INSERT OR IGNORE INTO topics(name, description, cluster_hint, user_reviewed) VALUES(?,?,?,0)",
            (t["name"], t["description"], t.get("cluster_hint") or None),
        )
        if cur.lastrowid:
            tid = cur.lastrowid
        else:
            row = conn.execute("SELECT id FROM topics WHERE name = ?", (t["name"],)).fetchone()
            tid = row["id"]
        for m in t["members"]:
            mn = normalize(m)
            if mn:
                member_to_topic[mn] = tid
    conn.commit()
    # map each chunk's concepts to topic_ids
    rows = conn.execute("SELECT id, chunk_id, raw_concepts FROM concept_extraction_log").fetchall()
    chunk_to_topics: defaultdict[int, set[int]] = defaultdict(set)
    for r in rows:
        try:
            arr = json.loads(r["raw_concepts"])
        except Exception:
            continue
        mapped: set[int] = set()
        for c in arr:
            tid = member_to_topic.get(normalize(c))
            if tid:
                mapped.add(tid)
        if mapped:
            chunk_to_topics[r["chunk_id"]].update(mapped)
            conn.execute(
                "UPDATE concept_extraction_log SET mapped_topic_ids = ? WHERE id = ?",
                (json.dumps(sorted(mapped)), r["id"]),
            )
    for chunk_id, topic_ids in chunk_to_topics.items():
        for tid in topic_ids:
            conn.execute(
                "INSERT OR IGNORE INTO chunk_topics(chunk_id, topic_id, relevance_score) VALUES(?,?,?)",
                (chunk_id, tid, 0.7),
            )
    conn.commit()
    conn.close()
    print(f"chunk-topic mappings written: {sum(len(v) for v in chunk_to_topics.values())}")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--min-count", type=int, default=2)
    args = p.parse_args()
    run(min_count=args.min_count)
