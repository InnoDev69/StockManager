from flask import Blueprint, jsonify, request, session
from bd.bdConector import BDConector
from debug.pydebug import DebugLogger
from bd.bdInstance import *
from debug.logger import logger
from data.validators import ItemValidator, UserValidator, ValidationError

api_bp = Blueprint("api", __name__)
debugger = DebugLogger()

def require_auth():
    """
    Verifica si el usuario está autenticado.
    Retorna un error JSON si no está autenticado.
    
    Requiere login: True.
    
    Returns:
        None si está autenticado, o una respuesta JSON de error si no lo está.
    """
    
    if not session.get("user_id"):
        return jsonify({"error": "No autorizado"}), 401
    return None

@api_bp.route("/health", methods=["GET"])
def health():
    """
    Endpoint de verificación de salud del servidor.
    
    Requiere login: False.
    
    Returns:
        JSON: {"status": "ok"} con código 200
    """
    return jsonify({"status": "ok"}), 200

@api_bp.route("/products_all", methods=["GET"])
def get_all_products():
    """
    Obtiene todos los productos del inventario con filtros opcionales.
    
    Requiere login: True.
    
    Query Parameters:
        search (str, optional): Búsqueda por nombre o código de barras
        view_mode (str, optional): Filtro por stock ("all", "in_stock", "out_of_stock")
    
    Returns:
        JSON: Lista de productos con sus detalles
        - id (int): ID del producto
        - barcode (str): Código de barras
        - name (str): Nombre del producto
        - description (str): Descripción
        - stock (int): Cantidad disponible
        - min_stock (int): Stock mínimo
        - price (float): Precio de venta
        - status (int): Estado del producto (1=activo, 0=deshabilitado)
    
    Status Codes:
        200: Éxito
        401: No autorizado
    """
    
    auth_error = require_auth()
    if auth_error:
        return auth_error
    
    search = request.args.get("search", "")
    view_mode = request.args.get("view_mode", "all")
    
    query = "SELECT id, barrs_code, name, description, quantity, min_quantity, price, status FROM items WHERE 1=1"
    params = []
    
    if search:
        query += " AND (name LIKE ? OR barrs_code LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    
    if view_mode == "in_stock":
        query += " AND quantity > 0"
    elif view_mode == "out_of_stock":
        query += " AND quantity = 0"
    
    rows = db.execute_query(query, tuple(params))
    
    products = [
        {
            "id": row[0],
            "barcode": row[1],
            "name": row[2],
            "description": row[3],
            "stock": row[4],
            "min_stock": row[5],
            "price": row[6],
            "status": row[7]
        }
        for row in rows
    ]
    
    return jsonify(products), 200

@api_bp.route("/products", methods=["GET"])
def get_products():
    """
    Obtiene todos los productos del inventario con filtros opcionales.
    
    Requiere login: True.
    
    Query Parameters:
        search (str, optional): Búsqueda por nombre o código de barras
        view_mode (str, optional): Filtro por stock ("all", "in_stock", "out_of_stock")
    
    Returns:
        JSON: Lista de productos con sus detalles
        - id (int): ID del producto
        - barcode (str): Código de barras
        - name (str): Nombre del producto
        - description (str): Descripción
        - stock (int): Cantidad disponible
        - min_stock (int): Stock mínimo
        - price (float): Precio de venta
        - status (int): Estado del producto (1=activo, 0=deshabilitado)
    
    Status Codes:
        200: Éxito
        401: No autorizado
    """
    
    auth_error = require_auth()
    if auth_error:
        return auth_error
    
    search = request.args.get("search", "")
    view_mode = request.args.get("view_mode", "all")
    
    query = "SELECT id, barrs_code, name, description, quantity, min_quantity, price, status FROM items WHERE status = 1"
    params = []
    
    if search:
        query += " AND (name LIKE ? OR barrs_code LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    
    if view_mode == "in_stock":
        query += " AND quantity > 0"
    elif view_mode == "out_of_stock":
        query += " AND quantity = 0"
    
    rows = db.execute_query(query, tuple(params))
    
    products = [
        {
            "id": row[0],
            "barcode": row[1],
            "name": row[2],
            "description": row[3],
            "stock": row[4],
            "min_stock": row[5],
            "price": row[6],
            "status": row[7]
        }
        for row in rows
    ]
    
    return jsonify(products), 200

@api_bp.route("/products/<int:product_id>", methods=["GET"])
def get_product(product_id):
    """
    Obtiene un producto específico por su ID (No muestra los deshabilitados).
    
    Requiere login: True.
    
    Args:
        product_id (int): ID del producto a buscar
    
    Returns:
        JSON: Detalles completos del producto
        - id (int): ID del producto
        - barcode (str): Código de barras
        - name (str): Nombre
        - description (str): Descripción
        - stock (int): Cantidad disponible
        - min_stock (int): Stock mínimo
        - price (float): Precio
    
    Status Codes:
        200: Producto encontrado
        401: No autorizado
        404: Producto no encontrado
    """
    
    auth_error = require_auth()
    if auth_error:
        return auth_error
    
    rows = db.execute_query(
        "SELECT id, barrs_code, name, description, quantity, min_quantity, price FROM items WHERE id = ?",
        (product_id,)
    )
    
    if not rows:
        return jsonify({"error": "Producto no encontrado"}), 404
    
    row = rows[0]
    product = {
        "id": row[0],
        "barcode": row[1],
        "name": row[2],
        "description": row[3],
        "stock": row[4],
        "min_stock": row[5],
        "price": row[6]
    }
    
    return jsonify(product), 200

@api_bp.route("/products", methods=["POST"])
def create_product():
    """
    Crea un nuevo producto en el inventario.
    
    Requiere login: True.
    Requiere rol: admin.
    
    Request Body (JSON):
        barcode (str): Código de barras del producto
        name (str): Nombre del producto
        description (str, optional): Descripción detallada
        quantity (int): Cantidad inicial en stock
        min_quantity (int): Stock mínimo de alerta
        price (float): Precio de venta
    
    Returns:
        JSON: {"message": "Producto creado exitosamente"}
    
    Status Codes:
        201: Producto creado exitosamente
        400: Faltan campos requeridos
        401: No autorizado
        403: Permiso denegado (no es admin)
        500: Error en la base de datos
    """
    
    auth_error = require_auth()
    if auth_error:
        return auth_error
    
    if session.get("role") != "admin":
        return jsonify({"error": "Permiso denegado"}), 403
    
    data = request.get_json()
    
    required_fields = ["barcode", "name", "quantity", "min_quantity", "price"]
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Faltan campos requeridos"}), 400
    
    try:
        db.add_item(
            data["barcode"],
            data.get("description", ""),
            data["name"],
            int(data["quantity"]),
            int(data["min_quantity"]),
            float(data["price"])
        )
        return jsonify({"message": "Producto creado exitosamente"}), 201
    
    except ValidationError as e:
        # Error de validación → 400 Bad Request
        return jsonify({"error": e.message, "field": e.field}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@api_bp.route("/products/<int:product_id>", methods=["PUT"])
def update_product(product_id):
    """
    Actualiza un producto existente.
    
    Requiere login: True.
    Requiere rol: admin.
    
    Args:
        product_id (int): ID del producto a actualizar
    
    Request Body (JSON):
        name (str, optional): Nuevo nombre
        description (str, optional): Nueva descripción
        quantity (int, optional): Nueva cantidad en stock
        min_quantity (int, optional): Nuevo stock mínimo
        price (float, optional): Nuevo precio
        status (int, optional): Nuevo estado (1=activo, 0=deshabilitado)
    
    Returns:
        JSON: {"message": "Producto actualizado"}
    
    Status Codes:
        200: Producto actualizado exitosamente
        400: No hay datos para actualizar
        401: No autorizado
        403: Permiso denegado (no es admin)
    """
    
    auth_error = require_auth()
    if auth_error:
        return auth_error
    
    if session.get("role") != "admin":
        return jsonify({"error": "Permiso denegado"}), 403
    
    data = request.get_json()
    
    updates = []
    params = []
    
    field_mapping = {
        "name": "name",
        "description": "description",
        "quantity": "quantity",
        "min_quantity": "min_quantity",
        "price": "price",
        "status": "status"
    }
    
    for key, db_field in field_mapping.items():
        if key in data:
            updates.append(f"{db_field} = ?")
            params.append(data[key])
    
    if not updates:
        return jsonify({"error": "No hay datos para actualizar"}), 400
    
    params.append(product_id)
    query = f"UPDATE items SET {', '.join(updates)} WHERE id = ?"
    
    db.execute_query(query, tuple(params), fetch=False)
    return jsonify({"message": "Producto actualizado"}), 200

@api_bp.route("/products/<int:product_id>", methods=["DELETE"])
def delete_product(product_id):
    """
    Elimina un producto del inventario.
    
    Requiere login: True.
    Requiere rol: admin.
    
    Args:
        product_id (int): ID del producto a eliminar
    
    Returns:
        JSON: {"message": "Producto eliminado"}
    
    Status Codes:
        200: Producto eliminado exitosamente
        401: No autorizado
        403: Permiso denegado (no es admin)
    """
    
    auth_error = require_auth()
    if auth_error:
        logger.error(f"Unauthorized delete attempt for product ID {product_id}")
        return auth_error
    
    if session.get("role") != "admin":
        logger.warning(f"Forbidden delete attempt for product ID {product_id} by user ID {session.get('user_id')}")
        return jsonify({"error": "Permiso denegado"}), 403
    
    db.disable_item(product_id)
    return jsonify({"message": "Producto eliminado"}), 200

@api_bp.route("/stats", methods=["GET"])
def get_stats():
    """
    Obtiene estadísticas del dashboard.
    
    Requiere login: True.
    
    Returns:
        JSON: Estadísticas del sistema
        - products (int): Total de productos
        - low_stock (int): Productos con stock bajo
        - sales_today (int): Ventas realizadas hoy
        - low_stock_list (array): Top 10 productos con stock crítico
          - id (int): ID del producto
          - name (str): Nombre
          - sku (str): Código de barras
          - stock (int): Cantidad actual
    
    Status Codes:
        200: Estadísticas obtenidas exitosamente
        401: No autorizado
    """
    
    auth_error = require_auth()
    if auth_error:
        return auth_error
    
    total_products = db.execute_query("SELECT COUNT(*) FROM items")[0][0]
    
    low_stock = db.execute_query(
        "SELECT COUNT(*) FROM items WHERE quantity <= min_quantity AND quantity > 0"
    )[0][0]
    
    sales_today = db.execute_query(
        "SELECT COUNT(*) FROM sells WHERE DATE(date) = DATE('now')"
    )[0][0]
    
    low_stock_items = db.execute_query(
        "SELECT id, name, barrs_code, quantity FROM items WHERE quantity <= min_quantity ORDER BY quantity ASC LIMIT 10"
    )
    
    low_stock_list = [
        {
            "id": row[0],
            "name": row[1],
            "sku": row[2],
            "stock": row[3]
        }
        for row in low_stock_items
    ]
    
    return jsonify({
        "products": total_products,
        "low_stock": low_stock,
        "sales_today": sales_today,
        "low_stock_list": low_stock_list
    }), 200

@api_bp.route("/sales", methods=["POST"])
def create_sale():
    """
    Registra una nueva venta de un producto.
    
    Requiere login: True.
    
    Request Body (JSON):
        barcode (str): Código de barras del producto
        quantity (int): Cantidad a vender
    
    Returns:
        JSON: Confirmación de venta
        - message (str): Mensaje de éxito
        - product (str): Nombre del producto vendido
        - quantity (int): Cantidad vendida
        - total (float): Total de la venta
    
    Status Codes:
        201: Venta registrada exitosamente
        400: Faltan campos requeridos o stock insuficiente
        401: No autorizado
        404: Producto no encontrado
    """
    
    auth_error = require_auth()
    if auth_error:
        return auth_error
    
    data = request.get_json()
    
    if "barcode" not in data or "quantity" not in data:
        return jsonify({"error": "Faltan campos requeridos"}), 400
    
    item = db.get_item_by_barcode(data["barcode"])
    
    if not item:
        return jsonify({"error": "Producto no encontrado"}), 404
    
    item_id, _, name, _, stock, price = item
    qty = int(data["quantity"])
    
    if stock < qty:
        return jsonify({"error": "Stock insuficiente"}), 400
    
    db.record_product_sale(item_id, qty)
    
    return jsonify({
        "message": f"Venta registrada: {name} x{qty}",
        "product": name,
        "quantity": qty,
        "total": price * qty
    }), 201

@api_bp.route("/sales/bulk", methods=["POST"])
def create_sales_bulk():
    """
    Registra una venta con múltiples productos.
    
    Requiere login: True.
    
    Request Body (JSON):
        items (array): Lista de productos a vender
          - item_id (int): ID del producto
          - quantity (int): Cantidad a vender
    
    Returns:
        JSON: Resultado de la operación
        - ok (bool): True si la venta fue exitosa
        - sale_id (int): ID de la venta creada
        - items (array): Lista de productos vendidos con detalles
        - total (float): Total de la venta
    
    Status Codes:
        201: Venta creada exitosamente
        400: Formato inválido o error en los datos
        401: No autorizado
    """
    
    auth_error = require_auth()
    if auth_error:
        return auth_error

    data = request.get_json(silent=True) or {}
    items = data.get("items", [])
    if not isinstance(items, list) or not items:
        return jsonify({"error": "Formato inválido: items[] requerido"}), 400

    validated_items = []
    resultados = []
    total = 0
    
    for idx, it in enumerate(items):
        try:
            item_id = int(it.get("item_id"))
            qty = int(it.get("quantity"))
        except (TypeError, ValueError):
            return jsonify({"error": f"item_id/cantidad inválidos en índice {idx}"}), 400

        row = db.execute_query("SELECT name, quantity, price FROM items WHERE id = ?", (item_id,))
        if not row:
            return jsonify({"error": f"Producto con ID {item_id} no encontrado"}), 400

        name, stock, price = row[0]
        if stock < qty:
            return jsonify({
                "error": "Stock insuficiente",
                "product": name,
                "requested": qty,
                "available": stock
            }), 400

        validated_items.append({"item_id": item_id, "quantity": qty})
        subtotal = round(price * qty, 2)
        resultados.append({
            "item_id": item_id,
            "name": name,
            "quantity": qty,
            "unit_price": price,
            "subtotal": subtotal
        })
        total += subtotal

    try:
        sale_id = db.record_bulk_sale(validated_items)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({
        "ok": True,
        "sale_id": sale_id,
        "items": resultados,
        "total": round(total, 2)
    }), 201

@api_bp.route("/sales", methods=["GET"])
def list_sales():
    """
    Lista las ventas registradas con filtros opcionales.
    
    Requiere login: True.
    
    Query Parameters:
        from (str, optional): Fecha inicial (formato: YYYY-MM-DD)
        to (str, optional): Fecha final (formato: YYYY-MM-DD)
    
    Returns:
        JSON: Lista de ventas agrupadas por ID
        - id (int): ID de la venta
        - date (str): Fecha y hora de la venta
        - items (array): Productos vendidos
          - product_name (str): Nombre del producto
          - quantity (int): Cantidad vendida
          - price (float): Precio unitario
        - total (float): Total de la venta
    
    Status Codes:
        200: Ventas obtenidas exitosamente
        401: No autorizado
    """
    
    auth_error = require_auth()
    if auth_error:
        return auth_error
    
    date_from = request.args.get("from")
    date_to = request.args.get("to")
    
    query = """
        SELECT s.id, s.date, d.item_id, i.name, d.quantity, d.price
        FROM sells s
        JOIN details d ON s.id = d.sell_id
        JOIN items i ON d.item_id = i.id
        WHERE 1=1
    """
    params = []
    
    if date_from:
        query += " AND DATE(s.date) >= ?"
        params.append(date_from)
    
    if date_to:
        query += " AND DATE(s.date) <= ?"
        params.append(date_to)
    
    query += " ORDER BY s.date DESC, s.id DESC"
    
    rows = db.execute_query(query, tuple(params))
    
    sales_dict = {}
    for row in rows:
        sale_id, date, item_id, name, quantity, price = row
        
        if sale_id not in sales_dict:
            sales_dict[sale_id] = {
                "id": sale_id,
                "date": date,
                "items": [],
                "total": 0
            }
        
        sales_dict[sale_id]["items"].append({
            "product_name": name,
            "quantity": quantity,
            "price": price
        })
        sales_dict[sale_id]["total"] += quantity * price
    
    sales = list(sales_dict.values())
    
    return jsonify(sales), 200
    
@api_bp.route("/items", methods=["GET"])
def search_items():
    """
    Busca productos para autocompletado.
    
    Requiere login: True.
    
    Query Parameters:
        q (str): Término de búsqueda (nombre o código de barras)
    
    Returns:
        JSON: Lista de hasta 10 productos coincidentes
        - id (int): ID del producto
        - barcode (str): Código de barras
        - name (str): Nombre
        - description (str): Descripción
        - stock (int): Cantidad disponible
        - price (float): Precio
    
    Status Codes:
        200: Búsqueda exitosa (puede retornar array vacío)
        401: No autorizado
    """
    
    auth_error = require_auth()
    if auth_error:
        return auth_error
    
    query_param = request.args.get("q", "").strip()
    if not query_param:
        return jsonify([]), 200
    
    rows = db.execute_query(
        "SELECT id, barrs_code, name, description, quantity, price FROM items WHERE barrs_code LIKE ? OR name LIKE ? LIMIT 10",
        (f"%{query_param}%", f"%{query_param}%")
    )
    
    items = [
        {
            "id": row[0],
            "barcode": row[1],
            "name": row[2],
            "description": row[3],
            "stock": row[4],
            "price": row[5]
        }
        for row in rows
    ]
    
    return jsonify(items), 200

@api_bp.route("/sales/<int:sale_id>", methods=["GET"])
def get_sale_detail(sale_id):
    """
    Obtiene los detalles de una venta específica.
    
    Requiere login: True.
    
    Args:
        sale_id (int): ID de la venta a consultar
    
    Returns:
        JSON: Detalles completos de la venta
        - id (int): ID de la venta
        - date (str): Fecha y hora de la venta
        - products (array): Lista de productos vendidos
          - name (str): Nombre del producto
          - quantity (int): Cantidad vendida
          - price (float): Precio unitario
        - total (float): Total de la venta
    
    Status Codes:
        200: Venta encontrada
        401: No autorizado
        404: Venta no encontrada
    """
    
    if not session.get("user_id"):
        return jsonify({"error": "Unauthorized"}), 401
    
    sale_data = db.execute_query(
        """
        SELECT s.id, s.date, i.name, d.quantity, d.price 
        FROM sells s 
        JOIN details d ON s.id = d.sell_id 
        JOIN items i ON d.item_id = i.id 
        WHERE s.id = ?
        """,
        (sale_id,)
    )
    
    if not sale_data:
        return jsonify({"error": "Sale not found"}), 404
    
    sale = {
        "id": sale_data[0][0],
        "date": sale_data[0][1],
        "products": [],
        "total": 0.0
    }
    
    for row in sale_data:
        product = {
            "name": row[2],
            "quantity": row[3],
            "price": float(row[4])
        }
        sale["products"].append(product)
        sale["total"] += product["quantity"] * product["price"]
    
    return jsonify(sale), 200, {'Content-Type': 'application/json'}