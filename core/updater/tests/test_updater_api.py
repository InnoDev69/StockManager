from functools import wraps

import pytest
from flask import Flask, jsonify, request

from core.updater.api import EXTENSION_KEY, create_updates_blueprint
from core.updater.service import UpdateError, UpdateInfo


class StubService:
    def __init__(self):
        self.checked, self.error = [], None

    def status(self):
        return UpdateInfo(current_version="v1.0.0", message="cache")

    def check(self, force=False):
        self.checked.append(force)
        return UpdateInfo(current_version="v1.0.0", latest_version="v1.1.0", update_available=True, can_apply=True)

    def apply(self):
        if self.error:
            raise self.error
        return "v1.1.0"


def build(auth=None):
    app = Flask(__name__)
    service = StubService()
    app.extensions[EXTENSION_KEY] = service
    app.register_blueprint(create_updates_blueprint(auth))
    return app.test_client(), service


def test_status_check_apply():
    client, service = build()
    assert client.get("/updates/status").get_json()["message"] == "cache"
    assert client.post("/updates/check", json={"force": True}).get_json()["latest_version"] == "v1.1.0"
    client.post("/updates/check")                                    # sin cuerpo
    assert service.checked == [True, False]
    res = client.post("/updates/apply")
    assert res.status_code == 202 and res.get_json()["tag"] == "v1.1.0"


def test_apply_errors_are_409_with_code():
    client, service = build()
    service.error = UpdateError("support_expired", "Renová el soporte.")
    res = client.post("/updates/apply")
    assert res.status_code == 409 and res.get_json() == {"error": "support_expired", "message": "Renová el soporte."}


def test_methods_are_restricted():
    client, _ = build()
    assert client.get("/updates/apply").status_code == 405
    assert client.post("/updates/status").status_code == 405


def test_auth_decorator_protects_everything():
    def only_admin(view):
        @wraps(view)
        def wrapped(*a, **kw):
            if request.headers.get("X-Role") != "admin":
                return jsonify(error="forbidden"), 403
            return view(*a, **kw)
        return wrapped

    client, _ = build(only_admin)
    assert client.get("/updates/status").status_code == 403
    assert client.post("/updates/check").status_code == 403
    assert client.post("/updates/apply").status_code == 403
    assert client.get("/updates/status", headers={"X-Role": "admin"}).status_code == 200
