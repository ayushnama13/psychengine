"""AI proposes prerequisite relationships between topics."""
from __future__ import annotations
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from psychengine.db import connect
from psychengine.ai.router import chat, parse_json


SYSTEM = """You design a learning order for psychology topics.
Given a list of topics with descriptions, propose prerequisite relationships.
Output strict JSON:
{"deps": [{"topic": "Topic A", "requires": ["Prereq Topic 1", "Prereq Topic 2"]}, ...]}

Rules:
- "requires" lists topics that MUST be understood first
- Foundational psychology theory (e.g., "Cognitive Biases", "Memory") usually has no prerequisites
- Applied tactics often require theory topics as prerequisites
- Keep dependencies sparse: only include strong prerequisite relationships
- Use exact topic names from the input
"""


def run():
    conn = connect()
    topics = conn.execute("SELECT id, name, description FROM topics ORDER BY name").fetchall()
    if not topics:
        print("no topics yet.")
        return
    listing = "\n".join(f"- {t['name']}: {t['description'] or ''}" for t in topics)
    user = f"Topics:\n{listing}\n\nReturn JSON only."
    resp, _ = chat(
        feature="topic_deps",
        system=SYSTEM,
        user=user,
        json_mode=True,
        temperature=0.2,
        max_tokens=4096,
    )
    data = parse_json(resp)
    deps = data.get("deps", []) if isinstance(data, dict) else []
    name_to_id = {t["name"]: t["id"] for t in topics}
    n_set = 0
    for entry in deps:
        tname = entry.get("topic")
        reqs = entry.get("requires", []) or []
        tid = name_to_id.get(tname)
        if not tid:
            continue
        req_ids = [name_to_id[r] for r in reqs if r in name_to_id and name_to_id[r] != tid]
        if req_ids:
            conn.execute(
                "UPDATE topics SET dependency_ids = ? WHERE id = ?",
                (json.dumps(req_ids), tid),
            )
            n_set += 1
    conn.commit()
    conn.close()
    print(f"set dependencies on {n_set} topics")


if __name__ == "__main__":
    run()
