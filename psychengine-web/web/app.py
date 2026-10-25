"""Flask app entrypoint."""
from __future__ import annotations
import json
import sys
from pathlib import Path

from flask import Flask, render_template, g

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from psychengine.db import connect


def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config["JSON_AS_ASCII"] = False

    @app.before_request
    def _open_db():
        g.db = connect()

    @app.teardown_request
    def _close_db(exc):
        db = getattr(g, "db", None)
        if db is not None:
            db.close()

    @app.context_processor
    def _injects():
        return {
            "app_name": "PsychEngine",
            "json": json,
        }

    @app.template_filter("days_ago_human")
    def days_ago_human(n):
        if n is None:
            return "never studied"
        if n == 0:
            return "studied today"
        if n == 1:
            return "studied 1 day ago"
        if n < 14:
            return f"studied {n} days ago"
        if n < 60:
            return f"studied {n//7} weeks ago"
        return f"last touched {n} days ago"

    @app.template_filter("decay_status")
    def decay_status(days):
        if days is None:
            return "attic"
        if days <= 3:
            return "fresh"
        if days <= 7:
            return "holding"
        if days <= 14:
            return "fading"
        if days <= 30:
            return "cold"
        if days <= 60:
            return "danger"
        return "attic"

    # blueprints
    from psychengine.web.routes.public import bp as public_bp
    from psychengine.web.routes.admin import bp as admin_bp
    from psychengine.web.routes.session import bp as session_bp
    from psychengine.web.routes.api import bp as api_bp
    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(session_bp, url_prefix="/session")
    app.register_blueprint(api_bp, url_prefix="/api")

    @app.route("/healthz")
    def healthz():
        return {"ok": True}

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8888, debug=True)
