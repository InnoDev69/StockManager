from miscellaneous import ROLES
from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from server.api.auth_utils import require_auth
from server.bd.bdInstance import db

settings_bp = Blueprint('settings', __name__)

@settings_bp.route("/settings", methods=["GET"])
@require_auth
def settings():
    """
    Página de configuración del usuario.
    
    Permite modificar:
    - Email
    - Contraseña
    - Otros datos de perfil
    
    Requiere login: True.
    
    Returns:
        Template: settings.html con datos del usuario actual
    """
    
    user_id = session.get("user_id")
    user_data = db.execute_query("SELECT username, email FROM users WHERE id = ?", (user_id,))
    user = None
    if user_data:
        user = {"username": user_data[0][0], "email": user_data[0][1]}
    
    return render_template("settings.html", user=user, role=session.get("role", ROLES.VENDOR), show_back=False)

