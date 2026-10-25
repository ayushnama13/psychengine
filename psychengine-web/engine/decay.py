"""Decay tracking + Ebbinghaus retention estimate."""
from __future__ import annotations
import math
import sys
from datetime import datetime, timedelta, date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from psychengine.db import connect


def parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", ""))
    except Exception:
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d")
        except Exception:
            return None


def decay_status_for(days: int | None) -> str:
    if days is None:
        return "attic"
    if days <= 3: return "fresh"
    if days <= 7: return "holding"
    if days <= 14: return "fading"
    if days <= 30: return "cold"
    if days <= 60: return "danger"
    return "attic"


def ebbinghaus(days: float, strength: float = 1.5) -> float:
    """Estimate retention given days since last engagement.
    strength scales with prior engagement count (1.0 = baseline, 2.0 = well-rehearsed)."""
    if days < 0:
        return 100.0
    s = max(0.3, strength)
    r = math.exp(-days / (s * 5.0))
    return max(0.0, min(100.0, r * 100.0))


def recompute_all():
    conn = connect()
    topics = conn.execute("SELECT id FROM topics WHERE user_reviewed = 1").fetchall()
    today = datetime.utcnow()
    for t in topics:
        tid = t["id"]
        last_row = conn.execute(
            "SELECT MAX(timestamp) ts, COUNT(*) n FROM topic_engagement_log WHERE topic_id = ?",
            (tid,),
        ).fetchone()
        last_ts = parse_dt(last_row["ts"]) if last_row and last_row["ts"] else None
        n = last_row["n"] if last_row else 0
        if last_ts is None:
            days = None
            retention = None
            status = "attic"
        else:
            days = max(0, (today - last_ts).days)
            strength = 1.0 + 0.25 * min(n, 8)
            retention = ebbinghaus(days, strength=strength)
            status = decay_status_for(days)
        conn.execute(
            "INSERT INTO topic_decay_state(topic_id, last_engaged_date, days_since_engagement, "
            "estimated_retention, decay_status, updated_at) VALUES(?,?,?,?,?, datetime('now')) "
            "ON CONFLICT(topic_id) DO UPDATE SET last_engaged_date=excluded.last_engaged_date, "
            "days_since_engagement=excluded.days_since_engagement, "
            "estimated_retention=excluded.estimated_retention, "
            "decay_status=excluded.decay_status, updated_at=datetime('now')",
            (tid, last_ts.isoformat() if last_ts else None, days, retention, status),
        )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    recompute_all()
    print("[ok] decay state recomputed")
