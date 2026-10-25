"""Session player routes."""
from __future__ import annotations
import json
from datetime import datetime

from flask import Blueprint, render_template, request, g, jsonify, redirect, url_for, abort

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
from psychengine.engine.session_gen import plan_today, mark_activity_complete, finalize_today
from psychengine.engine.scheduler import record_layer_complete
from psychengine.engine.decay import recompute_all

bp = Blueprint("session", __name__)


@bp.route("/today")
def player():
    plan = plan_today()
    return render_template("session/player.html", plan=plan)


@bp.route("/activity/<int:idx>")
def activity(idx):
    plan = plan_today()
    if idx < 0 or idx >= len(plan["activities"]):
        abort(404)
    act = plan["activities"][idx]
    nxt = idx + 1 if idx + 1 < len(plan["activities"]) else None
    prev = idx - 1 if idx > 0 else None
    ctx = {
        "plan": plan, "act": act, "idx": idx,
        "next_idx": nxt, "prev_idx": prev,
        "total": len(plan["activities"]),
    }
    kind = act["kind"]
    if kind == "layer":
        topic = g.db.execute("SELECT * FROM topics WHERE id = ?", (act["topic_id"],)).fetchone()
        chunks = g.db.execute(
            """SELECT c.id, c.text, c.chapter_name, b.title AS book_title, b.author, b.cluster
               FROM chunk_topics ct JOIN chunks c ON c.id = ct.chunk_id
               JOIN books b ON b.id = c.book_id
               WHERE ct.topic_id = ?
               ORDER BY (CASE b.cluster WHEN 'psychology_theory' THEN 0 ELSE 1 END), c.id
               LIMIT 6""",
            (act["topic_id"],),
        ).fetchall()
        ctx["topic"] = topic
        ctx["chunks"] = chunks
        return render_template(f"session/layer_{act['layer']}.html", **ctx)
    if kind == "morning_recall":
        recents = g.db.execute(
            """SELECT t.id, t.name FROM topic_engagement_log el
               JOIN topics t ON t.id = el.topic_id
               WHERE el.timestamp >= date('now', '-3 days')
               GROUP BY t.id ORDER BY MAX(el.timestamp) DESC LIMIT 4"""
        ).fetchall()
        ctx["recents"] = recents
        return render_template("session/morning_recall.html", **ctx)
    if kind == "mixed_practice":
        active = g.db.execute(
            """SELECT t.id, t.name, up.current_layer FROM user_progress up
               JOIN topics t ON t.id = up.topic_id
               WHERE up.current_layer >= 1
               ORDER BY RANDOM() LIMIT 5"""
        ).fetchall()
        ctx["active"] = active
        return render_template("session/mixed_practice.html", **ctx)
    if kind == "simulator":
        return render_template("session/simulator_stub.html", **ctx)
    if kind == "field_report":
        return render_template("session/field_report.html", **ctx)
    if kind == "end_of_day":
        today_log = g.db.execute(
            """SELECT t.name, el.engagement_type FROM topic_engagement_log el
               JOIN topics t ON t.id = el.topic_id
               WHERE date(el.timestamp) = date('now')
               ORDER BY el.timestamp DESC LIMIT 5"""
        ).fetchall()
        ctx["today_log"] = today_log
        return render_template("session/end_of_day.html", **ctx)
    return f"Unknown activity kind: {kind}", 400


@bp.post("/activity/<int:idx>/complete")
def complete_activity(idx):
    plan = plan_today()
    if idx < 0 or idx >= len(plan["activities"]):
        return jsonify({"ok": False}), 400
    act = plan["activities"][idx]
    data = request.get_json(silent=True) or {}
    if act["kind"] == "layer":
        score = data.get("score")
        record_layer_complete(act["topic_id"], act["layer"], score=score)
    mark_activity_complete(plan["date"], idx, payload=data)
    return jsonify({"ok": True, "next": idx + 1 if idx + 1 < len(plan["activities"]) else None})


@bp.post("/finalize")
def finalize():
    finalize_today()
    recompute_all()
    return jsonify({"ok": True})


@bp.post("/example")
def save_personal_example():
    data = request.get_json(force=True)
    topic_id = data.get("topic_id")
    text = (data.get("text") or "").strip()
    layer = data.get("layer")
    if not topic_id or not text:
        return jsonify({"ok": False}), 400
    g.db.execute(
        "INSERT INTO personal_examples(topic_id, layer, user_text) VALUES(?,?,?)",
        (topic_id, layer, text),
    )
    g.db.commit()
    return jsonify({"ok": True})
