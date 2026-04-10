from flask import Blueprint, render_template, session, redirect, url_for, flash
from api.auth_utils import require_admin

users_bp = Blueprint('users', __name__)

@users_bp.route("/users")
@require_admin
def users():
    """
    Página de gestión de usuarios.
    
    Requiere login: True.
    
    Returns:
        Template: users.html con la interfaz de gestión
    """
    
    return render_template("users.html")