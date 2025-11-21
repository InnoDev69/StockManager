from flask import Flask, redirect, render_template, session, request, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from bd.bdConector import BDConector
from api.API import *
import requests

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = "a"  # Cambiar en producción

db = BDConector("stock.db")
db.init_db()

app.register_blueprint(api_bp, url_prefix="/api")

def api_call(endpoint, method="GET", data=None):
    """Realiza llamadas internas a la API"""
    base_url = request.url_root.rstrip('/')
    url = f"{base_url}/api{endpoint}"
    
    with app.test_client() as client:
        if method == "GET":
            return client.get(url)
        elif method == "POST":
            return client.post(url, json=data)
        elif method == "PUT":
            return client.put(url, json=data)
        elif method == "DELETE":
            return client.delete(url)

@app.route("/")
def index():
    if not session.get("user_id"):
        return redirect("/login")
    
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["user_id"] = session.get("user_id")
            sess["role"] = session.get("role")
        
        stats_response = client.get("/api/stats")
        if stats_response.status_code == 200:
            stats_data = stats_response.get_json()
            stats = {
                "products": stats_data.get("products", 0),
                "low_stock": stats_data.get("low_stock", 0),
                "sales_today": stats_data.get("sales_today", 0)
            }
            low_stock_list = stats_data.get("low_stock_list", [])
        else:
            stats = {"products": 0, "low_stock": 0, "sales_today": 0}
            low_stock_list = []
    
    role = session.get("role", "Vendedor")
    return render_template('dashboard.html', stats=stats, role=role,
                           low_stock_list=low_stock_list, products=[])

@app.route("/login", methods=["GET"])
def login():
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def login_post():
    user = request.form.get("user", "").strip()
    password = request.form.get("password", "")
    if not user or not password:
        return render_template("login.html", error="Completa todos los campos")

    rows = db.execute_query("SELECT id, password, role FROM users WHERE username = ?", (user,))
    if not rows:
        return render_template("login.html", error="Usuario o contraseña inválidos")

    user_id, pw_hash, role_db = rows[0]
    if check_password_hash(pw_hash, password):
        session["user_id"] = user_id
        session["username"] = user
        session["role"] = role_db
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

@app.route("/products/new", methods=["GET", "POST"])
def product_new():
    if not session.get("user_id") or session.get("role") != "admin":
        return redirect(url_for("index"))
    if request.method == "GET":
        return render_template("product_form.html")
    # POST
    barrs_code = request.form.get("barrs_code", "").strip()
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    quantity = int(request.form.get("quantity", "0"))
    min_quantity = int(request.form.get("min_quantity", "0"))
    price = float(request.form.get("price", "0"))
    db.add_item(barrs_code, description, name, quantity, min_quantity, price)
    flash("Producto agregado")
    return redirect(url_for("index"))

@app.route("/product_form")
#Compatibilidad
def legacy_product_form():
    return redirect(url_for("product_new"))

@app.route("/sales/new", methods=["GET", "POST"])
def sale_new():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    if request.method == "GET":
        return render_template("sale_form.html")
    # POST
    barcode = request.form.get("barcode", "").strip()
    try:
        qty = int(request.form.get("quantity", "1"))
    except ValueError:
        return render_template("sale_form.html", error="Cantidad inválida")

    item = db.get_item_by_barcode(barcode)
    if not item:
        return render_template("sale_form.html", error="Producto no encontrado")

    # item: (id, barrs_code, name, description, quantity, price)
    item_id, barrs_code, name, description, stock, price = item

    if stock < qty:
        return render_template("sale_form.html", error="Stock insuficiente")
    db.record_sale(item_id, qty)
    flash(f"Venta registrada: {name} x{qty}")
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
