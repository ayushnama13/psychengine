"""Daily session planner."""
from __future__ import annotations
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from psychengine.config import SESSION_DEFAULT_MINUTES, NEW_TOPIC_INTERVAL_DAYS
from psychengine.db import connect
from psychengine.engine.scheduler import due_topics, candidates_for_new_intro


def _today_iso() -> str:
    return datetime.utcnow().date().isoformat()


def _last_new_intro_days_ago(conn) -> int:
    row = conn.execute(
        "SELECT MAX(date(layer_1_date)) d FROM user_progress WHERE layer_1_date IS NOT NULL"
    ).fetchone()
    if not row or not row["d"]:
        return 999
    d = datetime.fromisoformat(row["d"][:10]).date()
    return (datetime.utcnow().date() - d).days


def plan_today(session_minutes: int = SESSION_DEFAULT_MINUTES) -> dict:
    conn = connect()
    today = _today_iso()
    existing = conn.execute("SELECT * FROM daily_sessions WHERE date = ?", (today,)).fetchone()
    if existing and existing["planned_activities"]:
        conn.close()
        return {"date": today, "activities": json.loads(existing["planned_activities"]), "from_cache": True}

    activities: list[dict] = []
    activities.append({"kind": "morning_recall", "minutes": 2})

    # 1 due layer
    due = due_topics(today)
    if due:
        top = due[0]
        next_layer = (top["current_layer"] or 0) + 1
        activities.append({
            "kind": "layer",
            "topic_id": top["topic_id"],
            "topic_name": top["name"],
            "layer": next_layer,
            "minutes": [15, 15, 20, 25, 20, 15][next_layer],
        })

    # new topic intro if eligible
    if _last_new_intro_days_ago(conn) >= NEW_TOPIC_INTERVAL_DAYS:
        cands = candidates_for_new_intro(limit=1)
        if cands:
            c = cands[0]
            activities.append({
                "kind": "layer",
                "topic_id": c["topic_id"],
                "topic_name": c["name"],
                "layer": 1,
                "minutes": 15,
                "is_new": True,
            })

    activities.append({"kind": "mixed_practice", "minutes": 10})

    # simulator placeholder if a topic ≥ L3
    has_advanced = conn.execute(
        "SELECT COUNT(*) c FROM user_progress WHERE current_layer >= 3"
    ).fetchone()["c"] > 0
    activities.append({
        "kind": "simulator" if has_advanced else "field_report",
        "minutes": 10,
    })

    activities.append({"kind": "end_of_day", "minutes": 2})

    plan = {"date": today, "activities": activities, "from_cache": False}
    conn.execute(
        "INSERT OR REPLACE INTO daily_sessions(date, planned_activities, completed_activities) "
        "VALUES(?, ?, COALESCE((SELECT completed_activities FROM daily_sessions WHERE date = ?), '[]'))",
        (today, json.dumps(activities), today),
    )
    conn.commit()
    conn.close()
    return plan


def mark_activity_complete(date_iso: str, index: int, payload: dict | None = None):
    conn = connect()
    row = conn.execute("SELECT completed_activities FROM daily_sessions WHERE date = ?", (date_iso,)).fetchone()
    done = json.loads(row["completed_activities"]) if row and row["completed_activities"] else []
    done.append({"index": index, "at": datetime.utcnow().isoformat(), "payload": payload or {}})
    conn.execute("UPDATE daily_sessions SET completed_activities = ? WHERE date = ?", (json.dumps(done), date_iso))
    conn.commit()
    conn.close()


def finalize_today():
    """Mark session done, update streak."""
    conn = connect()
    today = _today_iso()
    conn.execute(
        "UPDATE daily_sessions SET completed = 1 WHERE date = ?", (today,)
    )
    # streak
    yesterday = (datetime.utcnow().date() - timedelta(days=1)).isoformat()
    prev = conn.execute("SELECT current_streak, longest_streak FROM streak_data WHERE date = ?", (yesterday,)).fetchone()
    prev_streak = prev["current_streak"] if prev else 0
    new_streak = prev_streak + 1
    longest = max(new_streak, prev["longest_streak"] if prev else 0)
    conn.execute(
        "INSERT OR REPLACE INTO streak_data(date, session_completed, current_streak, longest_streak) "
        "VALUES(?, 1, ?, ?)",
        (today, new_streak, longest),
    )
    conn.commit()
    conn.close()
