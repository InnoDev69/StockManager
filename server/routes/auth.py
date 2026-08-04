from flask import Blueprint, render_template, session, redirect, url_for

auth_bp = Blueprint('auth', __name__)

@auth_bp.route("/login", methods=["GET"])
def login():
    """
    Muestra el formulario de inicio de sesión.
    
    Requiere login: False.
    
    Returns:
        Template: login.html
    """
    
    if session.get("user_id"):
        return redirect(url_for("dashboard.index"))
    return render_template("login.html")

@auth_bp.route("/register", methods=["GET"])
def register(): 
    """
    Muestra el formulario de registro de nuevos usuarios.
    
    Requiere login: False.
    
    Returns:
        Template: login.html con parámetro register=True
    """
    
    return render_template("login.html", register=True)

@auth_bp.route("/logout")
def logout():
    """
    Cierra la sesión del usuario actual.
    
    Elimina todos los datos de sesión y redirige al login.
    
    Requiere login: True.
    
    Returns:
        Redirect: A la página de login
    """
    
    session.clear()
    return redirect(url_for("auth.login"))

@auth_bp.route("/reset-password", methods=["GET"])
def reset_password():
    """
    Muestra el formulario de restablecimiento de contraseña.
    
    Requiere login: False.
    
    Returns:
        Template: reset_password.html
    """
    
    return render_template("reset_password.html")