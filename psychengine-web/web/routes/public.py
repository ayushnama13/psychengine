"""Public-facing routes: dashboard, topics, books, reader, search."""
from __future__ import annotations
import json
from datetime import datetime, timedelta

from flask import Blueprint, render_template, request, g, abort, redirect, url_for

bp = Blueprint("public", __name__)


def _topic_cards():
    rows = g.db.execute(
        """
        SELECT t.id, t.name, t.description, t.cluster_hint,
               (SELECT COUNT(*) FROM chunk_topics ct WHERE ct.topic_id = t.id) AS n_chunks,
               up.current_layer, up.next_layer_due, up.mastery_score, up.status,
               ds.days_since_engagement AS days, ds.estimated_retention AS retention
        FROM topics t
        LEFT JOIN user_progress up ON up.topic_id = t.id
        LEFT JOIN topic_decay_state ds ON ds.topic_id = t.id
        WHERE t.user_reviewed = 1
        ORDER BY t.name
        """
    ).fetchall()
    return rows


@bp.route("/")
def dashboard():
    db = g.db
    n_topics = db.execute("SELECT COUNT(*) c FROM topics WHERE user_reviewed = 1").fetchone()["c"]
    n_books = db.execute("SELECT COUNT(*) c FROM books").fetchone()["c"]
    n_chunks = db.execute("SELECT COUNT(*) c FROM chunks").fetchone()["c"]
    n_mastered = db.execute(
        "SELECT COUNT(*) c FROM user_progress WHERE status = 'mastered'"
    ).fetchone()["c"]
    streak_row = db.execute("SELECT current_streak, longest_streak FROM streak_data ORDER BY date DESC LIMIT 1").fetchone()
    streak = streak_row["current_streak"] if streak_row else 0
    today = datetime.utcnow().date().isoformat()
    session_row = db.execute("SELECT * FROM daily_sessions WHERE date = ?", (today,)).fetchone()

    going_cold = db.execute(
        """SELECT t.id, t.name, ds.days_since_engagement, ds.estimated_retention
           FROM topic_decay_state ds JOIN topics t ON t.id = ds.topic_id
           WHERE ds.days_since_engagement >= 15
           ORDER BY ds.days_since_engagement DESC LIMIT 6"""
    ).fetchall()

    active_topics = db.execute(
        """SELECT t.id, t.name, t.cluster_hint, up.current_layer, up.mastery_score, up.next_layer_due,
                  ds.days_since_engagement AS days
           FROM user_progress up JOIN topics t ON t.id = up.topic_id
           LEFT JOIN topic_decay_state ds ON ds.topic_id = t.id
           WHERE up.status = 'active'
           ORDER BY up.next_layer_due ASC LIMIT 9"""
    ).fetchall()

    recent = db.execute(
        "SELECT id, date, context FROM field_reports ORDER BY date DESC LIMIT 3"
    ).fetchall()

    return render_template(
        "dashboard.html",
        stats={"topics": n_topics, "books": n_books, "chunks": n_chunks, "mastered": n_mastered, "streak": streak},
        session=session_row,
        going_cold=going_cold,
        active_topics=active_topics,
        recent=recent,
    )


@bp.route("/topics")
def topics_list():
    cluster = request.args.get("cluster")
    q = "SELECT t.id, t.name, t.description, t.cluster_hint, " \
        "(SELECT COUNT(*) FROM chunk_topics ct WHERE ct.topic_id = t.id) AS n_chunks, " \
        "up.current_layer, up.mastery_score, ds.days_since_engagement AS days " \
        "FROM topics t LEFT JOIN user_progress up ON up.topic_id = t.id " \
        "LEFT JOIN topic_decay_state ds ON ds.topic_id = t.id " \
        "WHERE t.user_reviewed = 1 "
    params: list = []
    if cluster:
        q += "AND t.cluster_hint = ? "
        params.append(cluster)
    q += "ORDER BY t.name"
    topics = g.db.execute(q, params).fetchall()
    clusters = [r["cluster_hint"] for r in g.db.execute(
        "SELECT DISTINCT cluster_hint FROM topics WHERE user_reviewed = 1 AND cluster_hint IS NOT NULL"
    ).fetchall()]
    return render_template("topics_list.html", topics=topics, clusters=clusters, current_cluster=cluster)


@bp.route("/topics/<int:topic_id>")
def topic_detail(topic_id):
    db = g.db
    topic = db.execute("SELECT * FROM topics WHERE id = ?", (topic_id,)).fetchone()
    if not topic:
        abort(404)
    progress = db.execute("SELECT * FROM user_progress WHERE topic_id = ?", (topic_id,)).fetchone()
    decay = db.execute("SELECT * FROM topic_decay_state WHERE topic_id = ?", (topic_id,)).fetchone()
    chunks = db.execute(
        """SELECT c.id, c.text, c.chapter_name, c.page_start, c.page_end,
                  b.title AS book_title, b.author, b.cluster, ct.relevance_score
           FROM chunk_topics ct
           JOIN chunks c ON c.id = ct.chunk_id
           JOIN books b ON b.id = c.book_id
           WHERE ct.topic_id = ?
           ORDER BY (CASE b.cluster WHEN 'psychology_theory' THEN 0 ELSE 1 END), b.title, c.chunk_index""",
        (topic_id,),
    ).fetchall()
    deps_raw = json.loads(topic["dependency_ids"] or "[]")
    deps = []
    if deps_raw:
        placeholders = ",".join("?" * len(deps_raw))
        deps = db.execute(
            f"SELECT id, name FROM topics WHERE id IN ({placeholders})", deps_raw
        ).fetchall()
    unlocks = db.execute(
        "SELECT id, name, dependency_ids FROM topics WHERE dependency_ids LIKE ?",
        (f"%{topic_id}%",),
    ).fetchall()
    unlocks = [u for u in unlocks if topic_id in json.loads(u["dependency_ids"] or "[]")]
    timeline = db.execute(
        "SELECT engagement_type, score, timestamp FROM topic_engagement_log WHERE topic_id = ? ORDER BY timestamp DESC LIMIT 30",
        (topic_id,),
    ).fetchall()
    examples = db.execute(
        "SELECT id, layer, user_text, timestamp FROM personal_examples WHERE topic_id = ? ORDER BY timestamp DESC",
        (topic_id,),
    ).fetchall()
    return render_template(
        "topic_detail.html",
        topic=topic, progress=progress, decay=decay,
        chunks=chunks, deps=deps, unlocks=unlocks,
        timeline=timeline, examples=examples,
    )


@bp.route("/books")
def books_list():
    cluster = request.args.get("cluster")
    q = "SELECT id, title, author, cluster, total_chunks FROM books "
    params: list = []
    if cluster:
        q += "WHERE cluster = ? "
        params.append(cluster)
    q += "ORDER BY cluster, title"
    books = g.db.execute(q, params).fetchall()
    clusters = [r["cluster"] for r in g.db.execute("SELECT DISTINCT cluster FROM books").fetchall()]
    return render_template("books_list.html", books=books, clusters=clusters, current_cluster=cluster)


@bp.route("/books/<int:book_id>")
def book_reader(book_id):
    db = g.db
    book = db.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
    if not book:
        abort(404)
    chapter = request.args.get("chapter")
    chunks_q = "SELECT id, chapter_name, chunk_index, text, page_start, page_end FROM chunks WHERE book_id = ?"
    params: list = [book_id]
    if chapter:
        chunks_q += " AND chapter_name = ?"
        params.append(chapter)
    chunks_q += " ORDER BY chunk_index"
    chunks = db.execute(chunks_q, params).fetchall()
    chapters = [r["chapter_name"] for r in db.execute(
        "SELECT chapter_name, MIN(chunk_index) ci FROM chunks WHERE book_id = ? GROUP BY chapter_name ORDER BY ci",
        (book_id,),
    ).fetchall()]
    # per-chunk topic markers
    chunk_ids = [c["id"] for c in chunks]
    topic_map: dict[int, list] = {}
    if chunk_ids:
        rows = db.execute(
            f"SELECT ct.chunk_id, t.id, t.name FROM chunk_topics ct JOIN topics t ON t.id = ct.topic_id "
            f"WHERE ct.chunk_id IN ({','.join('?' * len(chunk_ids))})",
            chunk_ids,
        ).fetchall()
        for r in rows:
            topic_map.setdefault(r["chunk_id"], []).append({"id": r["id"], "name": r["name"]})
    return render_template(
        "book_reader.html",
        book=book, chunks=chunks, chapters=chapters,
        current_chapter=chapter, topic_map=topic_map,
    )


@bp.route("/search")
def search():
    q = (request.args.get("q") or "").strip()
    results = []
    if q:
        try:
            fts_q = " ".join(f'"{w}"' for w in q.split())
            rows = g.db.execute(
                """SELECT c.id, snippet(chunks_fts, 0, '<mark>', '</mark>', '…', 24) AS snip,
                          c.chapter_name, c.page_start, b.title AS book_title, b.id AS book_id
                   FROM chunks_fts JOIN chunks c ON c.id = chunks_fts.rowid
                   JOIN books b ON b.id = c.book_id
                   WHERE chunks_fts MATCH ?
                   ORDER BY rank LIMIT 50""",
                (fts_q,),
            ).fetchall()
            results = rows
        except Exception as e:
            results = []
            error = str(e)
    return render_template("search.html", q=q, results=results)


@bp.route("/decay")
def decay():
    rows = g.db.execute(
        """SELECT t.id, t.name, t.cluster_hint, ds.days_since_engagement AS days,
                  ds.estimated_retention AS retention, ds.decay_status
           FROM topic_decay_state ds JOIN topics t ON t.id = ds.topic_id
           ORDER BY ds.estimated_retention ASC NULLS LAST"""
    ).fetchall()
    return render_template("decay.html", rows=rows)


@bp.route("/calendar")
def calendar():
    rows = g.db.execute(
        """SELECT date(timestamp) AS d, COUNT(*) n, AVG(score) avg_score
           FROM topic_engagement_log
           WHERE timestamp >= date('now', '-180 days')
           GROUP BY date(timestamp)"""
    ).fetchall()
    by_date = {r["d"]: {"n": r["n"], "avg": r["avg_score"] or 0} for r in rows}
    today = datetime.utcnow().date()
    cells = []
    for i in range(180, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        cells.append({"date": d, **(by_date.get(d) or {"n": 0, "avg": 0})})
    return render_template("calendar.html", cells=cells)


@bp.route("/settings")
def settings():
    rows = g.db.execute("SELECT key, value FROM settings").fetchall()
    settings_d = {r["key"]: r["value"] for r in rows}
    return render_template("settings.html", settings=settings_d)
