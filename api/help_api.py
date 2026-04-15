from flask import Blueprint, render_template, session, redirect, url_for
from api.auth_utils import require_auth

help_api = Blueprint('help', __name__)

@help_api.route("/help")
@require_auth
def help_center():
    """
    Centro de ayuda con guías para cada módulo.
    
    Requiere login: True.
    
    Returns:
        Template: help.html con contenido de ayuda por módulo
    """
    role = session.get("role", "vendedor")
    return render_template('help.html', role=role, show_back=False)