from datetime import date

import pytest
from flask import Flask, jsonify, render_template_string

from core.licensing.flask_integration import init_licensing, require_feature


def build_app(manager, auth=None):
    app = Flask(__name__)
    app.config["TESTING"] = True
    init_licensing(app, manager, auth_decorator=auth)

    @app.get("/multi")
    @require_feature("multicaja")
    def multi():
        return jsonify(ok=True)

    @app.get("/page")
    def page():
        return render_template_string(
            "{{ license_status().state.value }}|{{ 'si' if has_feature('marca_blanca') else 'no' }}"
        )
    return app


@pytest.fixture
def client(manager):
    return build_app(manager).test_client()


def test_status_endpoint(client):
    data = client.get("/api/license").get_json()
    assert data["state"] == "TRIAL" and data["trial_days_left"] == 30


def test_activate_ok_and_status(client, issue):
    token = issue(updates_until=date(2027, 11, 3), features={"multicaja": 2})
    res = client.post("/api/license/activate", json={"token": token})
    assert res.status_code == 200 and res.get_json()["state"] == "LICENSED"
    assert client.get("/api/license").get_json()["customer"] == "Kiosco Pepe"


@pytest.mark.parametrize("body, code", [
    ({"token": "basura"}, "invalid_format"),
    ({"token": ""}, "invalid_format"),
    ({"token": 123}, "invalid_format"),
    ({}, "invalid_format"),
    ({"token": "x" * 5000}, "invalid_format"),
])
def test_activate_bad_input(client, body, code):
    res = client.post("/api/license/activate", json=body)
    assert res.status_code == 400 and res.get_json()["error"] == code
    assert res.get_json()["message"]


def test_activate_wrong_machine_message_has_code(client, issue):
    res = client.post("/api/license/activate", json={"token": issue(machine="AAAA-AAAA-AAAA-AAAA")})
    data = res.get_json()
    assert res.status_code == 400 and data["error"] == "wrong_machine"
    assert "ABCD-EFGH-IJKL-2345" in data["message"]


def test_activate_without_json_body(client):
    assert client.post("/api/license/activate", data="x", content_type="text/plain").status_code == 400


def test_deactivate(client, issue):
    client.post("/api/license/activate", json={"token": issue()})
    assert client.post("/api/license/deactivate").get_json()["state"] == "TRIAL"


def test_require_feature(manager, issue):
    client = build_app(manager).test_client()
    res = client.get("/multi")
    assert res.status_code == 403 and res.get_json()["feature"] == "multicaja"
    manager.activate(issue(features={"multicaja": 2}))
    assert client.get("/multi").status_code == 200


def test_template_helpers(manager, issue):
    client = build_app(manager).test_client()
    assert client.get("/page").get_data(as_text=True) == "TRIAL|no"
    manager.activate(issue(features={"marca_blanca": True}))
    assert client.get("/page").get_data(as_text=True) == "LICENSED|si"


def test_auth_decorator_protects_all_routes(manager, issue):
    from functools import wraps
    from flask import request

    def only_admin(view):
        @wraps(view)
        def wrapped(*a, **kw):
            if request.headers.get("X-Role") != "admin":
                return jsonify(error="forbidden"), 403
            return view(*a, **kw)
        return wrapped

    client = build_app(manager, auth=only_admin).test_client()
    assert client.get("/api/license").status_code == 403
    assert client.post("/api/license/activate", json={"token": issue()}).status_code == 403
    assert client.post("/api/license/deactivate").status_code == 403
    assert client.get("/api/license", headers={"X-Role": "admin"}).status_code == 200
    assert client.post("/api/license/activate", json={"token": issue()}, headers={"X-Role": "admin"}).status_code == 200


def test_tab_template_and_static_are_served(client):
    app = client.application
    with app.test_request_context():
        from flask import render_template
        html = render_template("licensing/license_tab.html")
    assert 'id="license-tab"' in html and 'data-api="/api/license"' in html
    assert "/api/license/static/license-tab.js" in html
    res = client.get("/api/license/static/license-tab.js")
    assert res.status_code == 200 and b"StocklyLicenseTab" in res.data
