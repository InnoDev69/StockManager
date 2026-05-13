from data.validators import UserValidator, ValidationError
from data.variables import Var
from flask import Blueprint, app, render_template, request, session, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from bd.bdInstance import db
from data.roles import ROLES

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

@auth_bp.route("/login", methods=["POST"])
def login_post():
    """
    Procesa el inicio de sesión del usuario.
    
    Valida credenciales contra la base de datos y crea sesión si es válido.
    Utiliza hash de contraseñas con Werkzeug para seguridad.
    
    Requiere login: False.
    
    Form Data:
        user/email (str): Nombre de usuario o correo electrónico
        password (str): Contraseña en texto plano (se compara con hash)
    
    Returns:
        Redirect: Al dashboard si login exitoso, al formulario si falla
    """
    
    user = request.form.get("user", "").strip()
    password = request.form.get("password", "")
    if not user or not password:
        return render_template("login.html", error="Completa todos los campos")

    rows = db.execute_query("SELECT id, password, role, status FROM users WHERE username = ? OR email = ?", (user, user))
    if not rows:
        return render_template("login.html", error="Usuario o contraseña inválidos")

    user_id, pw_hash, role_db, status = rows[0]
    
    if status == 0:
        return render_template("login.html", error="Usuario desactivado. Contacta al administrador")
    
    if check_password_hash(pw_hash, password):
        session.permanent = True
        session["user_id"] = user_id
        session["username"] = user
        session["role"] = role_db
        return redirect(url_for("dashboard.index"))

    return render_template("login.html", error="Usuario o contraseña incorrectos")

@auth_bp.route("/register", methods=["GET"])
def register(): 
    """
    Muestra el formulario de registro de nuevos usuarios.
    
    Requiere login: False.
    
    Returns:
        Template: login.html con parámetro register=True
    """
    
    return render_template("login.html", register=True)

@auth_bp.route("/register", methods=["POST"])
def register_post():
    """
    Procesa el registro de un nuevo usuario.
    
    Crea un nuevo usuario en la base de datos con contraseña hasheada.
    Valida que el usuario/email no existan previamente.
    
    Requiere login: False.
    
    Form Data:
        user (str): Nombre de usuario único
        password (str): Contraseña (se almacena como hash)
        email (str): Correo electrónico
        role (str): Rol del usuario (default: 'user')
    
    Returns:
        Redirect: A login si registro exitoso, al formulario si falla
    """
    
    user = request.form.get("user", "").strip()
    password = request.form.get("password", "")
    email = request.form.get("email", "").strip()
    role = request.form.get("role", ROLES.VENDOR).strip()
    
    if role not in [ROLES.ADMIN, ROLES.VENDOR, ROLES.ROOT]:
        role = ROLES.VENDOR
    
    if not user or not password:
        return render_template("login.html", register=True, error="Completa todos los campos")

    if db.user_exists(user, email):
        return render_template("login.html", register=True, error="Usuario ya existe")
    
    try:
        UserValidator.validate_email(email)
    except ValidationError:
        return render_template("login.html", register=True, error="Email no válido")
    
    try:
        UserValidator.validate(user, password, email, role)
    except ValidationError as e:
        return render_template("login.html", register=True, error=str(e))

    pw_hash = generate_password_hash(password)
    db.add_user(user, pw_hash, email, ROLES.VENDOR, status=0, application=Var.USER_APPLICATION_PENDING)
    flash("Solicitud enviada. Espera aprobación del administrador.")
    flash("Cuenta creada. Inicia sesión.")
    return redirect(url_for("auth.login"))

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