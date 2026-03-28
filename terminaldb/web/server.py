"""Flask web server for terminalDB dashboard."""
from __future__ import annotations

import json
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from .. import db
from ..llm import LLMError

_STATIC  = Path(__file__).parent / "static"
_TMPL    = Path(__file__).parent / "templates"


def create_app() -> Flask:
    app = Flask(
        __name__,
        static_folder=str(_STATIC),
        template_folder=str(_TMPL),
    )
    app.config["JSON_SORT_KEYS"] = False

    # --- Security headers ---------------------------------------------------
    @app.after_request
    def _security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"]        = "DENY"
        response.headers["Access-Control-Allow-Origin"]  = "http://localhost:7777"
        response.headers["Access-Control-Allow-Methods"] = "GET, DELETE"
        return response

    # --- Routes -------------------------------------------------------------
    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/commands")
    def api_commands():
        return jsonify(db.fetch_all())

    @app.route("/api/commands/<int:record_id>", methods=["DELETE"])
    def api_delete(record_id: int):
        ok = db.delete_by_id(record_id)
        return jsonify({"ok": ok}), (200 if ok else 404)

    @app.route("/api/search/tags")
    def api_search_tags():
        tag     = request.args.get("tag", "").lower().strip()
        records = db.fetch_all()
        matched = [
            r for r in records
            if any(tag in t.lower() for t in r.get("tags", []))
        ]
        return jsonify(matched)

    @app.route("/api/search/ai")
    def api_search_ai():
        from ..llm import search_with_intent, suggest_only

        q = request.args.get("q", "").strip()
        if not q:
            return jsonify({"matched": [], "suggestions": [], "error": None})

        all_records = db.fetch_all()

        try:
            if not all_records:
                suggestions = suggest_only(q)
                return jsonify({"matched": [], "suggestions": suggestions, "error": None})

            result     = search_with_intent(q, all_records)
            ranked_ids = result.get("ranked_ids", [])
            id_map     = {r["id"]: r for r in all_records}
            matched    = [id_map[i] for i in ranked_ids if i in id_map]

            return jsonify({
                "matched":     matched,
                "suggestions": result.get("suggestions", []),
                "error":       None,
            })
        except LLMError as e:
            return jsonify({"matched": [], "suggestions": [], "error": str(e)})

    return app
