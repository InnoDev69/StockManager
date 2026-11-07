"""Integración con Flask: blueprint de la pestaña "Licencia" y `require_feature`."""
from __future__ import annotations

from functools import wraps
from typing import Callable

from flask import Blueprint, Flask, current_app, jsonify, request

from stockly_license import LicenseError

from .manager import LicenseManager
from .state import error_info

EXTENSION_KEY = "stockly_license_manager"
MAX_TOKEN_CHARS = 4096


def get_manager() -> LicenseManager:
    return current_app.extensions[EXTENSION_KEY]


def require_feature(name: str):
    """Como `require_role`, pero por función licenciada (p. ej. 'multicaja')."""

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not get_manager().has_feature(name):
                return jsonify(
                    error="feature_not_licensed",
                    feature=name,
                    message="Esta función no está incluida en tu licencia.",
                ), 403
            return view(*args, **kwargs)

        return wrapped

    return decorator


def create_license_blueprint(auth_decorator: Callable | None = None) -> Blueprint:
    """`auth_decorator` se aplica a todas las rutas (pasar p. ej. require_role(ROLES.ADMIN))."""
    bp = Blueprint(
        "licensing", __name__, url_prefix="/api/license",
        template_folder="templates", static_folder="static", static_url_path="/static",
    )
    protect = auth_decorator or (lambda view: view)

    def status_view():
        return jsonify(get_manager().status().to_dict())

    def activate_view():
        payload = request.get_json(silent=True) or {}
        token = payload.get("token")
        if not isinstance(token, str) or not token.strip() or len(token) > MAX_TOKEN_CHARS:
            return jsonify(error="invalid_format", message="Pegá el texto completo de la licencia."), 400
        manager = get_manager()
        try:
            status = manager.activate(token)
        except LicenseError as exc:
            code, message = error_info(exc, manager.machine_id)
            return jsonify(error=code, message=message), 400
        return jsonify(status.to_dict())

    def deactivate_view():
        return jsonify(get_manager().deactivate().to_dict())

    bp.add_url_rule("", "status", protect(status_view), methods=["GET"])
    bp.add_url_rule("/activate", "activate", protect(activate_view), methods=["POST"])
    bp.add_url_rule("/deactivate", "deactivate", protect(deactivate_view), methods=["POST"])
    return bp


def init_licensing(app: Flask, manager: LicenseManager, *, auth_decorator: Callable | None = None) -> None:
    """Registra el manager, las rutas `/api/license` y helpers para Jinja.

    En plantillas: `{{ license_status().state }}` y `{% if has_feature('marca_blanca') %}`.
    """
    app.extensions[EXTENSION_KEY] = manager
    app.context_processor(lambda: {"license_status": manager.status, "has_feature": manager.has_feature})
    app.register_blueprint(create_license_blueprint(auth_decorator))
