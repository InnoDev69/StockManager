from flask import jsonify, session

def require_auth():
    """
    Verifica si el usuario está autenticado.
    Retorna un error JSON si no está autenticado.
    
    Requiere login: True.
    
    Returns:
        None si está autenticado, o una respuesta JSON de error si no lo está.
    """
    
    user_id = session.get("user_id")
    #logger.info(f"require_auth check: user_id={user_id}, cookies={dict(request.cookies)}")
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    return None

def require_admin():
    """
    Verifica autenticación + rol admin.
    Retorna None si es admin, o una respuesta JSON de error.
    """
    auth_error = require_auth()
    if auth_error:
        return auth_error
    if session.get("role") != "admin":
        return jsonify({"error": "Permiso denegado"}), 403
    return None