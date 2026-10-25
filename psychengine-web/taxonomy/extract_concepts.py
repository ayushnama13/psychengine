"""For each chunk, extract raw concepts + 1-line gist via AI."""
from __future__ import annotations
import json
import sys
from pathlib import Path

from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from psychengine.db import connect
from psychengine.ai.router import chat, parse_json, AIError


SYSTEM = """You analyze psychology, persuasion, and social dynamics book excerpts.
Extract the key concepts, tactics, mental mechanisms, and named principles mentioned.
Output strictly valid JSON: {"gist": "<one-line summary>", "concepts": ["concept1", "concept2", ...]}
Rules:
- 3-8 concepts per chunk
- Use canonical names where possible (e.g., "reciprocity", "frame control", "loss aversion", "anchoring bias")
- Lowercase concept names, spaces allowed
- Skip generic filler ("introduction", "summary", "conclusion")
- If chunk is meta/table-of-contents/copyright, return {"gist": "meta", "concepts": []}
"""


def extract_for_chunk(chunk_id: int, text: str) -> dict | None:
    user = f"Excerpt:\n\n{text[:6000]}\n\nReturn JSON only."
    try:
        resp, engine = chat(
            feature="concept_extract",
            system=SYSTEM,
            user=user,
            json_mode=True,
            temperature=0.1,
            max_tokens=2048,
        )
        data = parse_json(resp)
        if not isinstance(data, dict):
            return None
        return {
            "gist": (data.get("gist") or "").strip()[:300],
            "concepts": [c.strip().lower() for c in (data.get("concepts") or []) if isinstance(c, str) and c.strip()][:10],
            "engine": engine,
        }
    except (AIError, ValueError, json.JSONDecodeError) as e:
        print(f"  [warn] chunk {chunk_id}: {e}")
        return None


def already_extracted(conn, chunk_id: int) -> bool:
    return conn.execute(
        "SELECT 1 FROM concept_extraction_log WHERE chunk_id = ? LIMIT 1", (chunk_id,)
    ).fetchone() is not None


def run(limit: int | None = None, book_id: int | None = None, min_tokens: int = 80):
    conn = connect()
    q = "SELECT id, text, token_estimate FROM chunks WHERE token_estimate >= ?"
    params: list = [min_tokens]
    if book_id is not None:
        q += " AND book_id = ?"
        params.append(book_id)
    q += " ORDER BY id"
    if limit:
        q += " LIMIT ?"
        params.append(limit)
    rows = conn.execute(q, params).fetchall()

    pending = [r for r in rows if not already_extracted(conn, r["id"])]
    print(f"Chunks pending extraction: {len(pending)} (of {len(rows)} total)")
    if not pending:
        return

    for r in tqdm(pending, desc="extracting"):
        result = extract_for_chunk(r["id"], r["text"])
        if not result:
            continue
        conn.execute(
            "INSERT INTO concept_extraction_log(chunk_id, raw_concepts, gist, ai_engine_used) "
            "VALUES(?,?,?,?)",
            (r["id"], json.dumps(result["concepts"]), result["gist"], result["engine"]),
        )
        conn.commit()
    conn.close()
    print("[ok] extraction done.")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int)
    p.add_argument("--book-id", type=int)
    p.add_argument("--min-tokens", type=int, default=80)
    args = p.parse_args()
    run(limit=args.limit, book_id=args.book_id, min_tokens=args.min_tokens)
