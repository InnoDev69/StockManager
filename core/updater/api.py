"""API de actualizaciones (/api/updates/...). Sin dependencias pesadas, para poder testearla."""
from __future__ import annotations

from typing import Callable

from flask import Blueprint, current_app, jsonify, request

from .service import UpdateError, UpdateService

EXTENSION_KEY = "stockly_update_service"


def get_service() -> UpdateService:
    return current_app.extensions[EXTENSION_KEY]


def create_updates_blueprint(auth_decorator: Callable | None = None) -> Blueprint:
    """`auth_decorator` se aplica a todas las rutas (p. ej. require_role(ROLES.ADMIN, ROLES.ROOT))."""
    bp = Blueprint("updates", __name__, url_prefix="/updates")
    protect = auth_decorator or (lambda view: view)

    def status_view():
        return jsonify(get_service().status().to_dict())

    def check_view():
        payload = request.get_json(silent=True) or {}
        return jsonify(get_service().check(force=bool(payload.get("force"))).to_dict())

    def apply_view():
        try:
            tag = get_service().apply()
        except UpdateError as exc:
            return jsonify(error=exc.code, message=exc.message), 409
        return jsonify(
            ok=True, tag=tag,
            message="Actualizando… Stockly se cerrará y volverá a abrirse en unos instantes.",
        ), 202

    bp.add_url_rule("/status", "status", protect(status_view), methods=["GET"])
    bp.add_url_rule("/check", "check", protect(check_view), methods=["POST"])
    bp.add_url_rule("/apply", "apply", protect(apply_view), methods=["POST"])
    return bp
