# api/auth_utils.py
from functools import wraps
from data.roles import ROLES
from flask import render_template, session, request, jsonify

def _wants_html():
    accept = request.headers.get("Accept", "")
    return "text/html" in accept

def _unauthenticated():
    if _wants_html():
        return render_template("login.html")
    return jsonify({"error": "Unauthorized", "message": "Authentication required"}), 401

def _forbidden():
    if _wants_html():
        return render_template("403.html"), 403
    return jsonify({"error": "Forbidden", "message": "Insufficient permissions"}), 403

def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user_id"):
            return _unauthenticated()
        return f(*args, **kwargs)
    return decorated_function

def require_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user_id"):
            return _unauthenticated()
        if session.get("role") != ROLES.ADMIN:
            return _forbidden()
        return f(*args, **kwargs)
    return decorated_function

def require_root(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user_id"):
            return _unauthenticated()
        if session.get("role") != ROLES.ROOT:
            return _forbidden()
        return f(*args, **kwargs)
    return decorated_function

def require_role(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get("user_id"):
                return _unauthenticated()
            if session.get("role") not in roles:
                return _forbidden()
            return f(*args, **kwargs)
        return decorated_function
    return decorator