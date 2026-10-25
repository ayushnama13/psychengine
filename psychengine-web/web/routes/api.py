"""Misc JSON endpoints."""
from __future__ import annotations
import json
from flask import Blueprint, request, g, jsonify

bp = Blueprint("api", __name__)


@bp.post("/highlight")
def add_highlight():
    data = request.get_json(force=True)
    chunk_id = data.get("chunk_id")
    text = (data.get("text") or "").strip()
    topic_id = data.get("topic_id")
    note = data.get("note", "")
    color = data.get("color", "yellow")
    if not chunk_id or not text:
        return jsonify({"ok": False, "error": "chunk_id + text required"}), 400
    cur = g.db.execute(
        "INSERT INTO highlights(chunk_id, topic_id, highlighted_text, user_note, color) VALUES(?,?,?,?,?)",
        (chunk_id, topic_id, text, note, color),
    )
    g.db.commit()
    return jsonify({"ok": True, "id": cur.lastrowid})


@bp.post("/field_report")
def add_field_report():
    data = request.get_json(force=True)
    cur = g.db.execute(
        "INSERT INTO field_reports(context, description, tactics_observed, what_worked, what_failed) "
        "VALUES(?,?,?,?,?)",
        (
            data.get("context", ""),
            data.get("description", ""),
            json.dumps(data.get("tactics_observed", [])),
            data.get("what_worked", ""),
            data.get("what_failed", ""),
        ),
    )
    g.db.commit()
    return jsonify({"ok": True, "id": cur.lastrowid})


@bp.post("/settings")
def set_setting():
    data = request.get_json(force=True)
    for k, v in data.items():
        g.db.execute(
            "INSERT OR REPLACE INTO settings(key, value) VALUES(?, ?)", (k, str(v))
        )
    g.db.commit()
    return jsonify({"ok": True})
