from flask import Blueprint, request, session, jsonify
from core.api.auth_utils import require_auth
from werkzeug.security import generate_password_hash, check_password_hash
from core.bd.bdInstance import db
from core.config import config
from miscellaneous.security import encode_text, decode_text, safe_decode, safe_encode

settings_api = Blueprint('settings_api', __name__)

# ════════════════════════════════════════════════════
# Settings API Endpoints
# ════════════════════════════════════════════════════

@settings_api.route("/settings/profile", methods=["PUT"])
@require_auth
def update_profile():
    """
    Actualizar información de perfil del usuario.
    
    JSON Body:
        email (str): Nuevo correo electrónico
    
    Returns:
        {
            "success": bool,
            "message": str,
            "error": str (only if error)
        }
    """
    try:
        data = request.get_json()
        email = data.get("email", "").strip()
        user_id = session.get("user_id")
        
        # Validación básica
        if not email:
            return {"error": "Email es requerido"}, 400
        
        if "@" not in email or "." not in email:
            return {"error": "Email inválido"}, 400
        
        # Actualizar email
        db.execute_query("UPDATE users SET email = ? WHERE id = ?", (email, user_id))
        
        return {
            "success": True,
            "message": "Perfil actualizado correctamente"
        }, 200
    
    except Exception as e:
        return {"error": str(e)}, 500

@settings_api.route("/settings/password", methods=["PUT"])
@require_auth
def change_password():
    """
    Cambiar contraseña del usuario.
    
    Valida contraseña actual antes de permitir el cambio.
    
    JSON Body:
        current_password (str): Contraseña actual
        new_password (str): Nueva contraseña
        confirm_password (str): Confirmación de nueva contraseña
    
    Returns:
        {
            "success": bool,
            "message": str,
            "error": str (only if error)
        }
    """
    try:
        data = request.get_json()
        current = data.get("current_password", "")
        new_pwd = data.get("new_password", "")
        confirm = data.get("confirm_password", "")
        user_id = session.get("user_id")
        
        # Validaciones
        if not current or not new_pwd or not confirm:
            return {"error": "Todos los campos son requeridos"}, 400
        
        if new_pwd != confirm:
            return {"error": "Las contraseñas nuevas no coinciden"}, 400
        
        if len(new_pwd) < 6:
            return {"error": "La contraseña debe tener al menos 6 caracteres"}, 400
        
        # Verificar contraseña actual
        user_data = db.execute_query("SELECT password FROM users WHERE id = ?", (user_id,))
        if not user_data or not check_password_hash(user_data[0][0], current):
            return {"error": "Contraseña actual incorrecta"}, 401
        
        # Generar nuevo hash y actualizar
        pw_hash = generate_password_hash(new_pwd)
        db.execute_query("UPDATE users SET password = ? WHERE id = ?", (pw_hash, user_id))
        
        return {
            "success": True,
            "message": "Contraseña actualizada correctamente"
        }, 200
    
    except Exception as e:
        return {"error": str(e)}, 500

EXCLUDED_KEYS = ["app", "ui"]

@settings_api.route("/settings/actual", methods=["GET"])
@require_auth
def get_all_settings():
    """Obtener todas las configuraciones actuales."""
    try:
        config_data = config.get_all(exclude=EXCLUDED_KEYS)
        
        if "roles" in config_data:
            decoded_roles = safe_decode(config_data["roles"])
            
            config_data["roles"] = decoded_roles
            
        return jsonify(config_data), 200
    except Exception as e:
        return {"success": False, "error": str(e)}, 500

@settings_api.route("/settings/actual/<string:key>", methods=["GET"])
@require_auth
def get_setting(key):
    """Obtener una configuración específica por clave."""
    try:
        value = config.get(key, exclude=EXCLUDED_KEYS)
        
        if value is None:
            return jsonify({"success": False, "error": f"Configuración '{key}' no encontrada"}), 404
        if key == "roles":
            value = safe_decode(value)
            
        return jsonify({key: value}), 200
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@settings_api.route("/settings/actual/<string:key>", methods=["PUT"])
@require_auth
def update_setting(key):
    """Actualizar una configuración específica por clave."""
    try:
        data = request.get_json() or {}
        value = data.get("value")
        
        if value is None:
            return jsonify({"success": False, "error": "El valor es requerido"}), 400
        
        if "roles" in key:
            config.set(key, safe_encode(value))
        else:
            config.set(key, value)
            
        return jsonify({
            "success": True,
            "message": f"Configuración '{key}' actualizada correctamente",
            "data": {key: value}
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500