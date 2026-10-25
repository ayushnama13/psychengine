"""Admin: book library + topic review (Phase 2 deliverable)."""
from __future__ import annotations
import json

from flask import Blueprint, render_template, request, g, jsonify, redirect, url_for

bp = Blueprint("admin", __name__)


@bp.route("/")
def index():
    db = g.db
    n_books = db.execute("SELECT COUNT(*) c FROM books").fetchone()["c"]
    n_chunks = db.execute("SELECT COUNT(*) c FROM chunks").fetchone()["c"]
    n_extracted = db.execute("SELECT COUNT(*) c FROM concept_extraction_log").fetchone()["c"]
    n_topics_total = db.execute("SELECT COUNT(*) c FROM topics").fetchone()["c"]
    n_topics_reviewed = db.execute("SELECT COUNT(*) c FROM topics WHERE user_reviewed = 1").fetchone()["c"]
    n_topics_pending = n_topics_total - n_topics_reviewed
    api_recent = db.execute(
        "SELECT feature, engine, COUNT(*) n, AVG(duration_ms) avg_ms FROM ai_api_log "
        "WHERE timestamp >= datetime('now', '-1 day') GROUP BY feature, engine"
    ).fetchall()
    books = db.execute(
        "SELECT id, title, author, cluster, total_chunks FROM books ORDER BY cluster, title"
    ).fetchall()
    return render_template(
        "admin/index.html",
        n_books=n_books, n_chunks=n_chunks, n_extracted=n_extracted,
        n_topics_total=n_topics_total, n_topics_reviewed=n_topics_reviewed,
        n_topics_pending=n_topics_pending,
        api_recent=api_recent,
        books=books,
    )


@bp.route("/topics")
def topics_review():
    show = request.args.get("show", "pending")  # pending | approved | all
    q = "SELECT t.id, t.name, t.description, t.cluster_hint, t.user_reviewed, " \
        "(SELECT COUNT(*) FROM chunk_topics ct WHERE ct.topic_id = t.id) AS n_chunks " \
        "FROM topics t"
    if show == "pending":
        q += " WHERE t.user_reviewed = 0"
    elif show == "approved":
        q += " WHERE t.user_reviewed = 1"
    q += " ORDER BY n_chunks DESC, t.name"
    topics = g.db.execute(q).fetchall()
    return render_template("admin/topics_review.html", topics=topics, show=show)


@bp.route("/topics/<int:tid>")
def topic_inspect(tid):
    db = g.db
    topic = db.execute("SELECT * FROM topics WHERE id = ?", (tid,)).fetchone()
    if not topic:
        return redirect(url_for("admin.topics_review"))
    chunks = db.execute(
        """SELECT c.id, c.text, c.chapter_name, b.title AS book_title, b.cluster
           FROM chunk_topics ct JOIN chunks c ON c.id = ct.chunk_id
           JOIN books b ON b.id = c.book_id
           WHERE ct.topic_id = ? ORDER BY b.cluster, b.title LIMIT 50""",
        (tid,),
    ).fetchall()
    all_topics = db.execute("SELECT id, name FROM topics WHERE id != ? ORDER BY name", (tid,)).fetchall()
    deps = json.loads(topic["dependency_ids"] or "[]")
    return render_template("admin/topic_inspect.html", topic=topic, chunks=chunks, all_topics=all_topics, deps=deps)


# ----- mutating endpoints -----

@bp.post("/topics/<int:tid>/approve")
def topic_approve(tid):
    g.db.execute("UPDATE topics SET user_reviewed = 1 WHERE id = ?", (tid,))
    g.db.commit()
    return jsonify({"ok": True})


@bp.post("/topics/<int:tid>/update")
def topic_update(tid):
    data = request.get_json(force=True)
    fields = []
    params = []
    for k in ("name", "description", "cluster_hint"):
        if k in data:
            fields.append(f"{k} = ?")
            params.append(data[k])
    if "dependency_ids" in data and isinstance(data["dependency_ids"], list):
        fields.append("dependency_ids = ?")
        params.append(json.dumps(data["dependency_ids"]))
    if not fields:
        return jsonify({"ok": False, "error": "no fields"}), 400
    params.append(tid)
    g.db.execute(f"UPDATE topics SET {', '.join(fields)}, modified_date = datetime('now') WHERE id = ?", params)
    g.db.commit()
    return jsonify({"ok": True})


@bp.post("/topics/<int:tid>/delete")
def topic_delete(tid):
    g.db.execute("DELETE FROM topics WHERE id = ?", (tid,))
    g.db.commit()
    return jsonify({"ok": True})


@bp.post("/topics/merge")
def topics_merge():
    data = request.get_json(force=True)
    src_ids = data.get("source_ids", [])
    target_id = data.get("target_id")
    if not src_ids or not target_id:
        return jsonify({"ok": False, "error": "need source_ids + target_id"}), 400
    db = g.db
    for sid in src_ids:
        if sid == target_id:
            continue
        # move chunk_topics
        db.execute(
            "INSERT OR IGNORE INTO chunk_topics(chunk_id, topic_id, relevance_score) "
            "SELECT chunk_id, ?, relevance_score FROM chunk_topics WHERE topic_id = ?",
            (target_id, sid),
        )
        db.execute("DELETE FROM chunk_topics WHERE topic_id = ?", (sid,))
        db.execute("DELETE FROM topics WHERE id = ?", (sid,))
    db.commit()
    return jsonify({"ok": True})


@bp.post("/topics/approve_all_pending")
def approve_all_pending():
    g.db.execute("UPDATE topics SET user_reviewed = 1 WHERE user_reviewed = 0")
    g.db.commit()
    return jsonify({"ok": True})


@bp.post("/chunks/<int:cid>/unmap_topic/<int:tid>")
def unmap_chunk_topic(cid, tid):
    g.db.execute("DELETE FROM chunk_topics WHERE chunk_id = ? AND topic_id = ?", (cid, tid))
    g.db.commit()
    return jsonify({"ok": True})


@bp.route("/books")
def books_admin():
    books = g.db.execute(
        "SELECT id, title, author, cluster, total_chunks, added_date FROM books ORDER BY added_date DESC"
    ).fetchall()
    return render_template("admin/books.html", books=books)


@bp.post("/books/<int:bid>/update")
def book_update(bid):
    data = request.get_json(force=True)
    fields = []
    params = []
    for k in ("title", "author", "cluster"):
        if k in data:
            fields.append(f"{k} = ?")
            params.append(data[k])
    if not fields:
        return jsonify({"ok": False}), 400
    params.append(bid)
    g.db.execute(f"UPDATE books SET {', '.join(fields)} WHERE id = ?", params)
    g.db.commit()
    return jsonify({"ok": True})


@bp.post("/books/<int:bid>/delete")
def book_delete(bid):
    g.db.execute("DELETE FROM books WHERE id = ?", (bid,))
    g.db.commit()
    return jsonify({"ok": True})


@bp.post("/topics/<int:tid>/start_progress")
def topic_start_progress(tid):
    """Initialize user_progress for a topic so it enters the layered system."""
    g.db.execute(
        "INSERT OR IGNORE INTO user_progress(topic_id, current_layer, status, next_layer_due) "
        "VALUES(?, 0, 'not_started', date('now'))",
        (tid,),
    )
    g.db.commit()
    return jsonify({"ok": True})
