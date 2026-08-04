from miscellaneous import ROLES
from flask import Blueprint, render_template, session
from server.api.auth_utils import require_auth, require_role

metrics_bp = Blueprint('metrics', __name__)

@metrics_bp.route("/metrics")
@require_auth
@require_role(ROLES.ADMIN, ROLES.ROOT)
def metrics():
    """
    Página de métricas y análisis.
    
    Requiere login: True.
    
    Returns:
        Template: metrics.html con gráficos e indicadores
    """
    
    return render_template("metrics.html", role=session.get('role', ROLES.VENDOR))