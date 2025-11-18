from flask import Flask, redirect, render_template, session, request, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from bd.bdConector import BDConector
from api.API import *

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = "a"  # Ccambiar

db = BDConector("stock.db")
db.init_db()

# Registro del blueprint desde api/API.py
app.register_blueprint(api_bp, url_prefix="/api")

@app.route("/")
def index():
    if not session.get("user_id"):
        return redirect("/login")
    return render_template("index.html")

@app.route("/login", methods=["GET"])
def login():
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def login_post():
    user = request.form.get("user", "").strip()
    password = request.form.get("password", "")
    if not user or not password:
        return render_template("login.html", error="Completa todos los campos")

    # Obtener id y hash de la BD
    rows = db.execute_query("SELECT id, password FROM users WHERE username = ?", (user,))
    if not rows:
        return render_template("login.html", error="Usuario o contraseña inválidos")

    user_id, pw_hash = rows[0]
    if check_password_hash(pw_hash, password):
        session["user_id"] = user_id
        session["username"] = user
        return redirect(url_for("index"))

    return render_template("login.html", error="Usuario o contraseña incorrectos")

@app.route("/register", methods=["GET"])
def register(): 
    return render_template("login.html", register=True)

@app.route("/register", methods=["POST"])
def register_post():
    user = request.form.get("user", "").strip()
    password = request.form.get("password", "")
    email = request.form.get("email", "").strip()
    role = request.form.get("role", "user")
    
    if not user or not password:
        return render_template("login.html", register=True, error="Completa todos los campos")

    if db.user_exists(user, email):
        return render_template("login.html", register=True, error="Usuario ya existe")

    pw_hash = generate_password_hash(password)
    db.add_user(user, pw_hash, email, role)
    flash("Cuenta creada. Inicia sesión.")
    return redirect(url_for("login"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

if __name__ == "__main__":
    # Ajusta host/port/debug según necesites
    app.run(host="0.0.0.0", port=5000, debug=True)
