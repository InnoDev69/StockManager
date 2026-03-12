from flask import Blueprint, render_template, session, redirect, url_for, flash

metrics_bp = Blueprint('metrics', __name__)

@metrics_bp.route("/metrics")
def metrics():
    """
    Página de métricas y análisis.
    
    Requiere login: True.
    
    Returns:
        Template: metrics.html con gráficos e indicadores
    """
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))
    
    role = session.get("role", "user")
    if role != "admin":
        flash("Acceso denegado", "error")
        return redirect(url_for("dashboard.index"))
    
    return render_template("metrics.html")