"""Scheduling: compute next layer due dates + adaptive spacing."""
from __future__ import annotations
import json
import sys
from datetime import datetime, timedelta, date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from psychengine.config import LAYER_INTERVALS
from psychengine.db import connect


def _today() -> date:
    return datetime.utcnow().date()


def next_due_for(progress: dict) -> str | None:
    """Given user_progress row dict, return ISO date of next layer due."""
    cur = progress.get("current_layer") or 0
    if cur >= 5:
        return None  # mastered
    last_field = f"layer_{cur}_date" if cur >= 1 else None
    next_layer = cur + 1
    interval = LAYER_INTERVALS.get(next_layer, 0)
    if not last_field or not progress.get(last_field):
        return _today().isoformat()
    last = datetime.fromisoformat(progress[last_field][:10]).date()
    return (last + timedelta(days=interval)).isoformat()


def adjust_interval_for_score(default_interval: int, score: float | None) -> int:
    """Adaptive: ace = longer, fail = shorter."""
    if score is None:
        return default_interval
    if score >= 95:
        return int(default_interval * 1.5)
    if score >= 80:
        return default_interval
    if score >= 60:
        return max(1, int(default_interval * 0.7))
    return max(1, int(default_interval * 0.4))


def record_layer_complete(topic_id: int, layer: int, score: float | None = None):
    """Mark layer N as completed today + schedule layer N+1."""
    conn = connect()
    today = _today().isoformat()
    # ensure user_progress exists
    conn.execute(
        "INSERT OR IGNORE INTO user_progress(topic_id, current_layer, status) VALUES(?, 0, 'active')",
        (topic_id,),
    )
    fld = f"layer_{layer}_date"
    next_layer = layer + 1
    if next_layer > 5:
        conn.execute(
            f"UPDATE user_progress SET {fld} = ?, current_layer = ?, status = 'mastered', "
            "next_layer_due = NULL, mastery_score = COALESCE(?, mastery_score) WHERE topic_id = ?",
            (today, layer, score, topic_id),
        )
    else:
        interval = LAYER_INTERVALS[next_layer]
        adjusted = adjust_interval_for_score(interval, score)
        due = (_today() + timedelta(days=adjusted)).isoformat()
        conn.execute(
            f"UPDATE user_progress SET {fld} = ?, current_layer = ?, status = 'active', "
            "next_layer_due = ? WHERE topic_id = ?",
            (today, layer, due, topic_id),
        )
    conn.execute(
        "INSERT INTO topic_engagement_log(topic_id, engagement_type, score, duration_seconds) VALUES(?,?,?,?)",
        (topic_id, f"layer_{layer}", score, 0),
    )
    conn.commit()
    conn.close()


def due_topics(today_iso: str | None = None) -> list[dict]:
    today_iso = today_iso or _today().isoformat()
    conn = connect()
    rows = conn.execute(
        """SELECT up.*, t.name, t.description, t.cluster_hint
           FROM user_progress up JOIN topics t ON t.id = up.topic_id
           WHERE up.next_layer_due IS NOT NULL AND up.next_layer_due <= ?
           ORDER BY up.next_layer_due ASC""",
        (today_iso,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def candidates_for_new_intro(limit: int = 3) -> list[dict]:
    """Topics with chunks but no user_progress yet."""
    conn = connect()
    rows = conn.execute(
        """SELECT t.id AS topic_id, t.name, t.description, t.cluster_hint,
                  (SELECT COUNT(*) FROM chunk_topics ct WHERE ct.topic_id = t.id) AS n_chunks
           FROM topics t LEFT JOIN user_progress up ON up.topic_id = t.id
           WHERE t.user_reviewed = 1 AND up.id IS NULL
           ORDER BY n_chunks DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
