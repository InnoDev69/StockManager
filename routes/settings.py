from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from api.auth_utils import require_auth, require_admin
from werkzeug.security import generate_password_hash, check_password_hash
from bd.bdInstance import db

settings_bp = Blueprint('settings', __name__)

@settings_bp.route("/settings", methods=["GET"])
@require_auth
def settings():
    """
    Página de configuración del usuario.
    
    Permite modificar:
    - Email
    - Contraseña
    - Otros datos de perfil
    
    Requiere login: True.
    
    Returns:
        Template: settings.html con datos del usuario actual
    """
    
    user_id = session.get("user_id")
    user_data = db.execute_query("SELECT username, email FROM users WHERE id = ?", (user_id,))
    user = None
    if user_data:
        user = {"username": user_data[0][0], "email": user_data[0][1]}
    
    return render_template("settings.html", user=user, show_back=False)

@settings_bp.route("/settings/profile", methods=["POST"])
@require_auth
def update_profile():
    """
    Actualizar información de perfil del usuario.
    
    Requiere login: True.
    
    Form Data:
        email (str): Nuevo correo electrónico
    
    Returns:
        Redirect: A página de configuración con mensaje de éxito/error
    """
    
    email = request.form.get("email", "").strip()
    user_id = session.get("user_id")
    
    if email:
        db.execute_query("UPDATE users SET email = ? WHERE id = ?", (email, user_id))
        flash("Perfil actualizado correctamente")
    else:
        flash("Email inválido", "error")
    
    return redirect(url_for("settings.settings"))

@settings_bp.route("/settings/password", methods=["POST"])
@require_auth
def change_password():
    """
    Cambiar contraseña del usuario.
    
    Valida contraseña actual antes de permitir el cambio.
    La nueva contraseña se almacena como hash.
    
    Requiere login: True.
    
    Form Data:
        current_password (str): Contraseña actual
        new_password (str): Nueva contraseña
        confirm_password (str): Confirmación de nueva contraseña
    
    Returns:
        Redirect: A configuración con mensaje de éxito/error
    """
    
    current = request.form.get("current_password", "")
    new_pwd = request.form.get("new_password", "")
    confirm = request.form.get("confirm_password", "")
    user_id = session.get("user_id")
    
    if new_pwd != confirm:
        flash("Las contraseñas nuevas no coinciden", "error")
        return redirect(url_for("settings.settings"))
    
    user_data = db.execute_query("SELECT password FROM users WHERE id = ?", (user_id,))
    if not user_data or not check_password_hash(user_data[0][0], current):
        flash("Contraseña actual incorrecta", "error")
        return redirect(url_for("settings.settings"))
    
    pw_hash = generate_password_hash(new_pwd)
    db.execute_query("UPDATE users SET password = ? WHERE id = ?", (pw_hash, user_id))
    flash("Contraseña actualizada correctamente")
    return redirect(url_for("settings.settings"))