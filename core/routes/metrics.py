from miscellaneous import ROLES, PERMS
from flask import Blueprint, render_template, session
from core.api.auth_utils import require_auth, require_permission
from templates.views import View

metrics_bp = Blueprint('metrics', __name__)

@metrics_bp.route("/metrics")
@require_auth
@require_permission(PERMS.METRICS_VIEW)
def metrics():
    """
    Página de métricas y análisis.
    
    Requiere login: True.
    
    Returns:
        Template: metrics.html con gráficos e indicadores
    """
    
    return render_template(View.METRICS.value, role=session.get('role', ROLES.VENDOR))