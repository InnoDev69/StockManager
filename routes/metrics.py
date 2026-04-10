from flask import Blueprint, render_template, session, redirect, url_for, flash
from api.auth_utils import require_auth, require_admin

metrics_bp = Blueprint('metrics', __name__)

@metrics_bp.route("/metrics")
@require_admin
def metrics():
    """
    Página de métricas y análisis.
    
    Requiere login: True.
    
    Returns:
        Template: metrics.html con gráficos e indicadores
    """
    
    return render_template("metrics.html")