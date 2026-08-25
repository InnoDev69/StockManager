"""
feature_highlights.py — Backend del sistema de "highlight" de features
nuevas en la UI.

Cada elemento nuevo en un template se marca con data-feature-id="algo".
El frontend (feature-highlights.js) le pregunta a este blueprint qué
feature_ids ya vio el usuario, y le avisa cuando ve uno nuevo. El estado
se guarda en el ConfigManager (namespace "ui"), no en localStorage del
navegador embebido, para que sea consistente sin importar el motor de
webview del SO.

Registrar en la app:
    from feature_highlights import bp as feature_highlights_bp
    app.register_blueprint(feature_highlights_bp)
"""

from flask import Blueprint, jsonify, request

from core.config import config

config.register_defaults("ui", {"seen_highlights": []})

bp = Blueprint("feature_highlights", __name__)

@bp.route("/ui/is-new", methods=["GET"])
def get_is_new():
    """retorna si el usuario a abierto la app por primera vez desde la instalación"""
    has_launched_before = bool(config.get("app.has_launched_before"))

    if not has_launched_before:
        config.set("app.has_launched_before", True)
        return jsonify({"is_new": True})

    return jsonify({"is_new": False})

@bp.route("/ui/seen-highlights", methods=["GET"])
def get_seen_highlights():
    seen = config.get("ui.seen_highlights", default=[])
    return jsonify({"seen": seen})

@bp.route("/ui/seen-highlights", methods=["POST"])
def add_seen_highlight():
    payload = request.get_json(silent=True) or {}
    feature_id = payload.get("feature_id")
    if not feature_id or not isinstance(feature_id, str):
        return jsonify({"error": "feature_id requerido"}), 400

    seen = config.get("ui.seen_highlights", default=[])
    if feature_id not in seen:
        seen = seen + [feature_id]
        config.set("ui.seen_highlights", seen)

    return jsonify({"seen": seen})