from flask import Blueprint, render_template, session, redirect, url_for, flash

users_bp = Blueprint('users', __name__)

@users_bp.route("/users")
def users():
    """
    Página de gestión de usuarios.
    
    Requiere login: True.
    
    Returns:
        Template: users.html con la interfaz de gestión
    """
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))
    
    role = session.get("role", "user")
    if role != "admin":
        flash("Acceso denegado", "error")
        return redirect(url_for("dashboard.index"))
    
    return render_template("users.html")