from flask import Blueprint, render_template, session
from data.roles import ROLES

help_bp = Blueprint('help', __name__)

@help_bp.route("/help")
def help_center():
    """
    Centro de ayuda con guías para cada módulo.
    
    Requiere login: True.
    
    Returns:
        Template: help.html con contenido de ayuda por módulo
    """
    role = session.get("role", ROLES.VENDOR)
    return render_template('help.html', role=role, show_back=False)
