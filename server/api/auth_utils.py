# api/auth_utils.py
from functools import wraps
from flask import jsonify, render_template, request, session
from miscellaneous import ROLES
from server.services import permissions_service

def require_permission(*permissions):
    """
    Autoriza si el usuario tiene AL MENOS UNO de los permisos dados.
    Uso:
        @require_permission(PERMS.PRODUCTS_MANAGE)
        @require_permission(PERMS.SALES_EDIT, PERMS.SALES_VIEW_ALL)  # OR
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get("user_id"):
                return _unauthorized()
            role = session.get("role")
            if role == ROLES.ROOT:
                return f(*args, **kwargs)  # root siempre tiene todo
            if not any(permissions_service.has_permission(role, perm) for perm in permissions):
                return _forbidden()
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def _is_api_request() -> bool:
    """
    Determina si la petición espera JSON en lugar de HTML.
    Se considera API si cumple cualquiera de estas condiciones:
      - La ruta empieza con /api/
      - El cliente envía el header X-Requested-With: XMLHttpRequest
      - El cliente acepta JSON mejor que HTML (fetch sin Accept explícito no cumple esto,
        por eso las dos condiciones anteriores son más confiables)
    """
    if request.path.startswith("/api/"):
        return True
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return True
    best = request.accept_mimetypes.best_match(["application/json", "text/html"])
    return best == "application/json"

def _unauthorized():
    if _is_api_request():
        return jsonify({"error": "No autenticado"}), 401
    return render_template("login.html")

def _forbidden():
    if _is_api_request():
        return jsonify({"error": "Permiso denegado"}), 403
    return render_template("403.html"), 403

def require_role(*roles):
    """
    Decorador unificado de autenticación y autorización.

    Sin argumentos válidos actúa como require_auth (solo verifica sesión).
    Con roles, verifica que el rol del usuario esté en la lista.

    Uso:
        @require_role()                        # solo autenticado
        @require_role(ROLES.ADMIN)             # admin
        @require_role(ROLES.ROOT, ROLES.ADMIN) # root o admin
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get("user_id"):
                return _unauthorized()
            if roles and session.get("role") not in roles:
                return _forbidden()
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Aliases de conveniencia (opcionales, para no romper código existente)
require_auth  = require_role()
require_admin = require_role(ROLES.ADMIN)
require_root  = require_role(ROLES.ROOT)