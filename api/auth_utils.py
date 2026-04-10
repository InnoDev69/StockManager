# api/auth_utils.py
from functools import wraps
from tempfile import template
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
            return jsonify({"error": "Unauthorized"}), 401
        
        if session.get("role") != "admin":
            return jsonify({"error": "Permiso denegado"}), 403
        
        return f(*args, **kwargs)
    return decorated_function

def require_role(role_required):
    """
    Decorador parametrizado: Verifica un rol específico.
    
    Uso:
        @require_role("admin")
        def create_product():
            pass
        
        @require_role("vendedor")
        def create_sale():
            pass
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = session.get("user_id")
            if not user_id:
                return jsonify({"error": "Unauthorized"}), 401
            
            user_role = session.get("role")
            if user_role != role_required:
                return jsonify({"error": f"Se requiere rol: {role_required}"}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator