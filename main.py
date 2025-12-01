from flask import Flask, redirect, render_template, session, request, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from bd.bdConector import BDConector
from api.API import *
from bd.bdInstance import *
import requests
import csv
import io
import uuid

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = "a"  # Cambiar en producción

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
    
    # Llamada directa a BD en lugar de HTTP interno
    stats_data = db.get_dashboard_stats()
    stats = {
        "products": stats_data.get("products", 0),
        "low_stock": stats_data.get("low_stock", 0),
        "sales_today": stats_data.get("sales_today", 0)
    }
    low_stock_list = stats_data.get("low_stock_list", [])
    
    role = session.get("role", "Vendedor")
    return render_template('dashboard.html', stats=stats, role=role,
                           low_stock_list=low_stock_list, products=[], show_back=False)

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

@app.route("/settings", methods=["GET"])
def settings():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    
    user_id = session.get("user_id")
    user_data = db.execute_query("SELECT username, email FROM users WHERE id = ?", (user_id,))
    user = None
    if user_data:
        user = {"username": user_data[0][0], "email": user_data[0][1]}
    
    return render_template("settings.html", user=user)

@app.route("/settings/profile", methods=["POST"])
def update_profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    
    email = request.form.get("email", "").strip()
    user_id = session.get("user_id")
    
    if email:
        db.execute_query("UPDATE users SET email = ? WHERE id = ?", (email, user_id))
        flash("Perfil actualizado correctamente")
    else:
        flash("Email inválido", "error")
    
    return redirect(url_for("settings"))

@app.route("/settings/password", methods=["POST"])
def change_password():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    
    current = request.form.get("current_password", "")
    new_pwd = request.form.get("new_password", "")
    confirm = request.form.get("confirm_password", "")
    user_id = session.get("user_id")
    
    if new_pwd != confirm:
        flash("Las contraseñas nuevas no coinciden", "error")
        return redirect(url_for("settings"))
    
    # Verificar contraseña actual
    user_data = db.execute_query("SELECT password FROM users WHERE id = ?", (user_id,))
    if not user_data or not check_password_hash(user_data[0][0], current):
        flash("Contraseña actual incorrecta", "error")
        return redirect(url_for("settings"))
    
    # Actualizar
    pw_hash = generate_password_hash(new_pwd)
    db.execute_query("UPDATE users SET password = ? WHERE id = ?", (pw_hash, user_id))
    flash("Contraseña actualizada correctamente")
    return redirect(url_for("settings"))

@app.route("/sales", methods=["GET"])
def sales():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    
    # Agrupar ventas por sell_id
    sales_data = db.execute_query(
        "SELECT s.id, s.date, i.name, d.quantity, d.price "
        "FROM sells s "
        "JOIN details d ON s.id = d.sell_id "
        "JOIN items i ON d.item_id = i.id "
        "ORDER BY s.date DESC"
    )
    
    # Estructurar ventas agrupadas
    sales_dict = {}
    for row in sales_data:
        sale_id = row[0]
        if sale_id not in sales_dict:
            sales_dict[sale_id] = {
                "id": sale_id,
                "date": row[1],
                "products": [],
                "total": 0.0,
                "total_quantity": 0
            }
        
        sales_dict[sale_id]["products"].append({
            "name": row[2],
            "quantity": row[3],
            "price": row[4]
        })
        sales_dict[sale_id]["total"] += row[3] * row[4]
        sales_dict[sale_id]["total_quantity"] += row[3]
    
    sales = list(sales_dict.values())
    return render_template("sales.html", sales=sales)

# Almacenamiento temporal para preview
temp_imports = {}

@app.route("/import", methods=["GET"])
def import_preview():
    if not session.get("user_id") or session.get("role") != "admin":
        return redirect(url_for("index"))
    
    if request.method == "GET":
        return render_template("import.html")
    
    # POST: procesar CSV
    if 'file' not in request.files:
        return {"error": "No file"}, 400
    
    file = request.files['file']
    delimiter = request.form.get('delimiter', ',')
    has_header = request.form.get('has_header') == '1'
    
    content = file.read().decode('utf-8')
    reader = csv.reader(io.StringIO(content), delimiter=delimiter)
    rows = list(reader)
    
    if not rows:
        return {"error": "Empty file"}, 400
    
    headers = rows[0] if has_header else [f"Col{i}" for i in range(len(rows[0]))]
    data_rows = rows[1:] if has_header else rows
    
    # Guardar temporalmente
    temp_key = str(uuid.uuid4())
    temp_imports[temp_key] = {
        'headers': headers,
        'rows': data_rows,
        'delimiter': delimiter
    }
    
    return {
        'temp_key': temp_key,
        'headers': headers,
        'rows': data_rows[:10]  # Preview solo 10
    }

@app.route("/import/confirm", methods=["POST"])
def confirm_import():
    if not session.get("user_id") or session.get("role") != "admin":
        return redirect(url_for("index"))
    
    temp_key = request.form.get('temp_key')
    if temp_key not in temp_imports:
        flash("Sesión expirada, vuelve a subir el CSV", "error")
        return redirect(url_for('import_preview'))
    
    data = temp_imports.pop(temp_key)
    rows = data['rows']
    
    # Mapeo
    col_barcode = int(request.form.get('col_barcode', 0))
    col_name = int(request.form.get('col_name', 1))
    col_description = int(request.form.get('col_description', 2))
    col_quantity = int(request.form.get('col_quantity', 3))
    col_min_quantity = int(request.form.get('col_min_quantity', 4))
    col_price = int(request.form.get('col_price', 5))
    
    imported = 0
    for row in rows:
        if len(row) <= max(col_barcode, col_name, col_quantity, col_price):
            continue
        
        barcode = row[col_barcode].strip()
        name = row[col_name].strip()
        desc = row[col_description].strip() if col_description < len(row) else ""
        qty = int(row[col_quantity]) if row[col_quantity].isdigit() else 0
        min_qty = int(row[col_min_quantity]) if col_min_quantity < len(row) and row[col_min_quantity].isdigit() else 0
        price = float(row[col_price]) if col_price < len(row) else 0.0
        
        db.add_item(barcode, desc, name, qty, min_qty, price)
        imported += 1
    
    flash(f"{imported} productos importados correctamente")
    return redirect(url_for('index'))

@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
