from flask import Flask, redirect, render_template, session, request, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from api.API import *
from bd.bdInstance import *
from data.limits import Limits
from debug.logger import logger
import requests
import csv
import io
import uuid
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.getenv("FLASK_SECRET_KEY", "a")

# Context processor para hacer Limits disponible en todas las plantillas
@app.context_processor
def inject_limits():
    return {'Limits': Limits}

app.register_blueprint(api_bp, url_prefix="/api")

def api_call(endpoint, method="GET", data=None):
    """
    Realiza llamadas internas a la API REST.
    Requiere login: True.
    
    Args:
        endpoint (str): Endpoint de la API (ej. '/items', '/sales')
        method (str): Método HTTP ('GET', 'POST', 'PUT', 'DELETE')
        data (dict, optional): Datos para enviar en métodos POST/PUT
    
    Returns:
        Response: Objeto de respuesta de Flask con el resultado de la API
    
    Ejemplo:
        response = api_call('/items', 'POST', {'name': 'Producto'})
    """
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

#@app.route("/product_management")
def under_development():
    """Página de funcionalidad en desarrollo."""
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return render_template("under_development.html")

@app.route("/")
def index():
    """
    Dashboard principal de la aplicación.
    
    Muestra estadísticas generales:
    - Total de productos
    - Productos con stock bajo
    - Ventas del día
    - Lista de productos con stock crítico
    
    Requiere login: True.
    
    Returns:
        Template: dashboard.html con estadísticas y datos del usuario
    """
    
    if not session.get("user_id"):
        return redirect("/login")
    
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
    """
    Muestra el formulario de inicio de sesión.
    
    Requiere login: False.
    
    Returns:
        Template: login.html
    """
    
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def login_post():
    """
    Procesa el inicio de sesión del usuario.
    
    Valida credenciales contra la base de datos y crea sesión si es válido.
    Utiliza hash de contraseñas con Werkzeug para seguridad.
    
    Requiere login: False.
    
    Form Data:
        user (str): Nombre de usuario
        password (str): Contraseña en texto plano (se compara con hash)
    
    Returns:
        Redirect: Al dashboard si login exitoso, al formulario si falla
    """
    
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
    """
    Muestra el formulario de registro de nuevos usuarios.
    
    Requiere login: False.
    
    Returns:
        Template: login.html con parámetro register=True
    """
    
    return render_template("login.html", register=True)

@app.route("/register", methods=["POST"])
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
    """
    Cierra la sesión del usuario actual.
    
    Elimina todos los datos de sesión y redirige al login.
    
    Requiere login: True.
    
    Returns:
        Redirect: A la página de login
    """
    
    session.clear()
    return redirect(url_for("login"))

@app.route("/products/new", methods=["GET", "POST"])
def product_new():
    """
    Crear un nuevo producto en el inventario.
    
    Solo usuarios con rol 'admin' pueden acceder.
    
    Requiere login: True.
    
    GET: Muestra formulario de creación
    POST: Procesa y guarda el nuevo producto
    
    Form Data (POST):
        barrs_code (str): Código de barras del producto
        name (str): Nombre del producto
        description (str): Descripción detallada
        quantity (int): Cantidad en stock inicial
        min_quantity (int): Stock mínimo (alerta de bajo stock)
        price (float): Precio de venta
    
    Returns:
        Template/Redirect: Formulario en GET, redirect a dashboard en POST
    """
    
    if not session.get("user_id") or session.get("role") != "admin":
        return redirect(url_for("index"))
    
    empty_form = {
        "barrs_code": "",
        "name": "",
        "description": "",
        "quantity": 0,
        "min_quantity": 0,
        "price": "0.00"
    }
    
    if request.method == "GET":
        return render_template("product_form.html", form_data=empty_form)

    form_data = {
        "barrs_code": request.form.get("barrs_code", "").strip(),
        "name": request.form.get("name", "").strip(),
        "description": request.form.get("description", "").strip(),
        "quantity": request.form.get("quantity", "0"),
        "min_quantity": request.form.get("min_quantity", "0"),
        "price": request.form.get("price", "0")
    }
    
    try:
        quantity = int(form_data["quantity"])
        min_quantity = int(form_data["min_quantity"])
        price = float(form_data["price"])
        
        db.add_item(
            form_data["barrs_code"],
            form_data["description"],
            form_data["name"],
            quantity,
            min_quantity,
            price
        )
        flash("Producto agregado")
        return redirect(url_for("index"))
    
    except ValidationError as e:
        return render_template(
            "product_form.html",
            error=e.message,
            error_field=e.field,
            form_data=form_data
        )
    except (ValueError, TypeError) as e:
        return render_template(
            "product_form.html",
            error="Valor numérico inválido",
            form_data=form_data
        )

@app.route("/product_form")
#Compatibilidad
def legacy_product_form():
    return redirect(url_for("product_new"))

@app.route("/sales/new", methods=["GET", "POST"])
def sale_new():
    """
    Crear una nueva venta.
    
    Requiere login: True.
    
    GET: Muestra formulario de venta
    POST: Procesa y registra la venta
    
    Form Data (POST):
        barcode (str): Código de barras del producto
        quantity (int): Cantidad vendida
    
    Returns:
        Template/Redirect: Formulario en GET, redirect a dashboard en POST
    """
    
    if not session.get("user_id"):
        return redirect(url_for("login"))
    if request.method == "GET":
        return render_template("sale_form.html")
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
    
    if not session.get("user_id"):
        return redirect(url_for("login"))
    
    user_id = session.get("user_id")
    user_data = db.execute_query("SELECT username, email FROM users WHERE id = ?", (user_id,))
    user = None
    if user_data:
        user = {"username": user_data[0][0], "email": user_data[0][1]}
    
    return render_template("settings.html", user=user, show_back=False)

@app.route("/settings/profile", methods=["POST"])
def update_profile():
    """
    Actualizar información de perfil del usuario.
    
    Requiere login: True.
    
    Form Data:
        email (str): Nuevo correo electrónico
    
    Returns:
        Redirect: A página de configuración con mensaje de éxito/error
    """
    
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
    
    if not session.get("user_id"):
        return redirect(url_for("login"))
    
    current = request.form.get("current_password", "")
    new_pwd = request.form.get("new_password", "")
    confirm = request.form.get("confirm_password", "")
    user_id = session.get("user_id")
    
    if new_pwd != confirm:
        flash("Las contraseñas nuevas no coinciden", "error")
        return redirect(url_for("settings"))
    
    user_data = db.execute_query("SELECT password FROM users WHERE id = ?", (user_id,))
    if not user_data or not check_password_hash(user_data[0][0], current):
        flash("Contraseña actual incorrecta", "error")
        return redirect(url_for("settings"))
    
    pw_hash = generate_password_hash(new_pwd)
    db.execute_query("UPDATE users SET password = ? WHERE id = ?", (pw_hash, user_id))
    flash("Contraseña actualizada correctamente")
    return redirect(url_for("settings"))

@app.route("/sales", methods=["GET"])
def sales():
    """
    Muestra el historial de ventas.
    
    Requiere login: True.
    
    Returns:
        Template: sales.html con datos de ventas
    """
    
    if not session.get("user_id"):
        return redirect(url_for("login"))
    
    sales_data = db.execute_query(
        "SELECT s.id, s.date, i.name, d.quantity, d.price "
        "FROM sells s "
        "JOIN details d ON s.id = d.sell_id "
        "JOIN items i ON d.item_id = i.id "
        "ORDER BY s.date DESC"
    )
    
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

temp_imports = {}

@app.route("/import", methods=["GET"])
def import_preview():
    """
    Vista previa de importación CSV.
    
    Solo administradores pueden importar productos.
    Muestra las primeras filas del CSV para mapear columnas.
    
    Requiere login: True.
    
    Returns:
        Template: import.html con formulario de importación
        JSON: Vista previa de datos si es POST (legacy support)
    """
    
    if not session.get("user_id") or session.get("role") != "admin":
        return redirect(url_for("index"))
    
    if request.method == "GET":
        return render_template("import.html")
    
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
    
    temp_key = str(uuid.uuid4())
    temp_imports[temp_key] = {
        'headers': headers,
        'rows': data_rows,
        'delimiter': delimiter
    }
    
    return {
        'temp_key': temp_key,
        'headers': headers,
        'rows': data_rows[:10]
    }

@app.route("/import/confirm", methods=["POST"])
def confirm_import():
    """
    Confirmar e importar productos desde CSV.
    
    Procesa el archivo CSV temporal, mapea columnas según configuración
    del usuario e inserta productos en la base de datos.
    
    Requiere login: True.
    
    Form Data:
        temp_key (str): UUID del archivo temporal
        col_barcode (int): Índice de columna para código de barras
        col_name (int): Índice de columna para nombre
        col_description (int): Índice de columna para descripción
        col_quantity (int): Índice de columna para cantidad
        col_min_quantity (int): Índice de columna para stock mínimo
        col_price (int): Índice de columna para precio
    
    Returns:
        Redirect: A dashboard con mensaje de productos importados
    """
    
    if not session.get("user_id") or session.get("role") != "admin":
        return redirect(url_for("index"))
    
    temp_key = request.form.get('temp_key')
    if temp_key not in temp_imports:
        flash("Sesión expirada, vuelve a subir el CSV", "error")
        return redirect(url_for('import_preview'))
    
    data = temp_imports.pop(temp_key)
    rows = data['rows']
    
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
    """
    Manejador de error 404 - Página no encontrada.
    
    Requiere login: False.
    
    Args:
        e: Objeto de excepción
    
    Returns:
        Template: 404.html con código de estado 404
    """
    logger.warning(f"404 - Ruta no encontrada: {request.path}")
    return render_template("404.html"), 404

@app.errorhandler(500)
def internal_error(e):
    """Manejador de error 500 - Error interno del servidor."""
    logger.exception(f"500 - Error interno: {request.path}")
    return render_template("404.html"), 500

@app.errorhandler(Exception)
def handle_exception(e):
    """Manejador global de excepciones no capturadas."""
    logger.exception(f"Excepción no capturada en {request.path}: {str(e)}")
    return render_template("404.html"), 500

@app.route("/product_management")
def product_management():
    """
    Página de administración de productos.
    
    Permite ver, editar y eliminar productos del inventario.
    Solo accesible para usuarios autenticados.
    
    Requiere login: True.
    
    Returns:
        Template: product_management.html con la interfaz de gestión
    """
    if not session.get("user_id"):
        return redirect(url_for("login"))
    
    role = session.get("role", "user")
    if role != "admin":
        pass
    
    return render_template("product_management.html")

@app.route("/metrics")
def metrics():
    """
    Página de métricas y análisis.
    
    Requiere login: True.
    
    Returns:
        Template: metrics.html con gráficos e indicadores
    """
    if not session.get("user_id"):
        return redirect(url_for("login"))
    
    role = session.get("role", "user")
    if role != "admin":
        pass
    
    return render_template("metrics.html")

if __name__ == "__main__":
    port = int(os.environ.get("FLASK_PORT", 5000))
    logger.info(f"Iniciando servidor en puerto {port}")
    app.run(host="127.0.0.1", port=port, debug=True if 
            os.environ.get("FLASK_ENV", "production") == "development" else False)
