from data.roles import ROLES
from flask import Blueprint, render_template, session
from api.auth_utils import require_role

users_bp = Blueprint('users', __name__)

@users_bp.route("/users")
@require_role(ROLES.ROOT)
def users():
    """
    Página de gestión de usuarios.
    
    Requiere login: True.
    
    Returns:
        Template: users.html con la interfaz de gestión
    """
    
    return render_template("users.html", role=session.get('role', ROLES.VENDOR))