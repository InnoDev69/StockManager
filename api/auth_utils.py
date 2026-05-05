# api/auth_utils.py
from functools import wraps
from tempfile import template
from data.roles import ROLES
from flask import jsonify, render_template, render_template, session

def require_auth(f):
    """
    Decorador: Verifica que usuario esté autenticado.
    
    Uso:
        @require_auth
        def get_products():
            # user_id ya está disponible en session
            username = session.get("username")
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id:
            return render_template("login.html")
        return f(*args, **kwargs)
    return decorated_function

def require_admin(f):
    """
    Decorador: Verifica autenticación + rol admin.
    
    Uso:
        @require_admin
        def create_product():
            # Solo llega acá si está autenticado Y es admin
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id:
            return render_template("login.html")
        
        if session.get("role") != ROLES.ADMIN:
            return render_template("403.html"), 403
        
        return f(*args, **kwargs)
    return decorated_function

def require_root(f):
    """
    Decorador: Verifica autenticación + rol root.
    
    Uso:
        @require_root
        def delete_user():
            # Solo llega acá si está autenticado Y es root
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id:
            return render_template("login.html")
        
        if session.get("role") != ROLES.ROOT:
            return render_template("403.html"), 403
        
        return f(*args, **kwargs)
    return decorated_function

def require_role(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get("user_id"):
                return render_template("login.html")

            if session.get("role") not in roles:
                return render_template("403.html"), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator