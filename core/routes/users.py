from miscellaneous import ROLES
from flask import Blueprint, render_template, session
from miscellaneous.permissions import PERMS
from core.api.auth_utils import require_permission

from templates.views import View

users_bp = Blueprint('users', __name__)

@users_bp.route("/users")
@require_permission(PERMS.USERS_MANAGE)
def users():
    """
    Página de gestión de usuarios.
    
    Requiere login: True.
    
    Returns:
        Template: users.html con la interfaz de gestión
    """
    
    return render_template(View.USERS.value, role=session.get('role', ROLES.VENDOR))