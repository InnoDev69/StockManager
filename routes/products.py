import csv
import io
import time
import uuid
from api.auth_utils import require_auth, require_admin
from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from api.notifications_api import notify_user
from bd.bdInstance import db
from bd.bdConector import ValidationError
from tools import logger

products_bp = Blueprint('products', __name__)

temp_imports = {}
TEMP_IMPORT_MAX_AGE = 1800  # 30 minutos
TEMP_IMPORT_MAX_ENTRIES = 20

def cleanup_temp_imports():
    """Elimina importaciones temporales expiradas (>30 min) o si hay demasiadas."""
    now = time.time()
    expired = [k for k, v in temp_imports.items()
               if now - v.get("created_at", 0) > TEMP_IMPORT_MAX_AGE]
    for k in expired:
        del temp_imports[k]
    
    # Si aún hay demasiadas, eliminar las más antiguas
    if len(temp_imports) > TEMP_IMPORT_MAX_ENTRIES:
        sorted_keys = sorted(temp_imports, key=lambda k: temp_imports[k].get("created_at", 0))
        for k in sorted_keys[:len(temp_imports) - TEMP_IMPORT_MAX_ENTRIES]:
            del temp_imports[k]

@products_bp.route("/products/new", methods=["GET", "POST"])
@require_admin
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
    
    if request.form.get("barrs_code", "").strip() == "":
        flash("El código de barras no puede estar vacío", "error")
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
        
        return redirect(url_for("dashboard.index"))
    
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
        
#Compatibilidad
def legacy_product_form():
    return redirect(url_for("products.product_new"))

@products_bp.route("/product_management")
@require_admin
def product_management():
    """
    Página de administración de productos.
    
    Permite ver, editar y eliminar productos del inventario.
    Solo accesible para usuarios autenticados.
    
    Requiere login: True.
    
    Returns:
        Template: product_management.html con la interfaz de gestión
    """
    
    return render_template("product_management.html")

@products_bp.route("/import", methods=["GET"])
@require_admin
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
    
    cleanup_temp_imports()
    
    temp_key = str(uuid.uuid4())
    temp_imports[temp_key] = {
        'headers': headers,
        'rows': data_rows,
        'delimiter': delimiter,
        'created_at': time.time()
    }
    
    return {
        'temp_key': temp_key,
        'headers': headers,
        'rows': data_rows[:10]
    }
    
@products_bp.route("/import/confirm", methods=["POST"])
@require_admin
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
    
    temp_key = request.form.get('temp_key')
    if temp_key not in temp_imports:
        flash("Sesión expirada, vuelve a subir el CSV", "error")
        return redirect(url_for('products.import_preview'))
    
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
    return redirect(url_for('dashboard.index'))

@products_bp.route("/products/<int:product_id>")
@require_auth
def product_detail(product_id):
    """
    Detalles de un producto específico.
    
    Muestra información completa del producto, incluyendo stock y fecha de vencimiento.
    Solo usuarios autenticados pueden acceder.
    
    Requiere login: True.
    
        Args:
                product_id (int): ID del producto a mostrar
    
    """
    product = db.get_item_by_id(product_id)
    return render_template("product_detail.html", product=product)