from flask import Blueprint, jsonify, request, session
from bd.bdConector import BDConector

api_bp = Blueprint("api", __name__)
db = BDConector("stock.db")

# Middleware para verificar autenticación en endpoints protegidos
def require_auth():
    if not session.get("user_id"):
        return jsonify({"error": "No autorizado"}), 401
    return None

@api_bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200

@api_bp.route("/products", methods=["GET"])
def get_products():
    """Obtiene todos los productos con filtros opcionales"""
    auth_error = require_auth()
    if auth_error:
        return auth_error
    
    # Filtros opcionales
    search = request.args.get("search", "")
    view_mode = request.args.get("view_mode", "all")
    
    query = "SELECT id, barrs_code, name, description, quantity, min_quantity, price FROM items WHERE 1=1"
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
            "price": row[6]
        }
        for row in rows
    ]
    
    return jsonify(products), 200

@api_bp.route("/products/<int:product_id>", methods=["GET"])
def get_product(product_id):
    """Obtiene un producto específico por ID"""
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
    """Crea un nuevo producto (solo admin)"""
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
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@api_bp.route("/products/<int:product_id>", methods=["PUT"])
def update_product(product_id):
    """Actualiza un producto existente (solo admin)"""
    auth_error = require_auth()
    if auth_error:
        return auth_error
    
    if session.get("role") != "admin":
        return jsonify({"error": "Permiso denegado"}), 403
    
    data = request.get_json()
    
    # Construir query dinámica según campos presentes
    updates = []
    params = []
    
    field_mapping = {
        "name": "name",
        "description": "description",
        "quantity": "quantity",
        "min_quantity": "min_quantity",
        "price": "price"
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
    """Elimina un producto (solo admin)"""
    auth_error = require_auth()
    if auth_error:
        return auth_error
    
    if session.get("role") != "admin":
        return jsonify({"error": "Permiso denegado"}), 403
    
    db.execute_query("DELETE FROM items WHERE id = ?", (product_id,), fetch=False)
    return jsonify({"message": "Producto eliminado"}), 200

@api_bp.route("/stats", methods=["GET"])
def get_stats():
    """Obtiene estadísticas del dashboard"""
    auth_error = require_auth()
    if auth_error:
        return auth_error
    
    # Total de productos
    total_products = db.execute_query("SELECT COUNT(*) FROM items")[0][0]
    
    # Productos con stock bajo
    low_stock = db.execute_query(
        "SELECT COUNT(*) FROM items WHERE quantity <= min_quantity AND quantity > 0"
    )[0][0]
    
    # Ventas de hoy
    sales_today = db.execute_query(
        "SELECT COUNT(*) FROM sells WHERE DATE(date) = DATE('now')"
    )[0][0]
    
    # Lista de productos con bajo stock
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
    """Registra una nueva venta"""
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
    """Registra una venta con múltiples items: body { items: [{item_id, quantity}] }"""
    auth_error = require_auth()
    if auth_error:
        return auth_error

    data = request.get_json(silent=True) or {}
    items = data.get("items", [])
    if not isinstance(items, list) or not items:
        return jsonify({"error": "Formato inválido: items[] requerido"}), 400

    resultados = []
    errores = []

    for idx, it in enumerate(items):
        try:
            item_id = int(it.get("item_id"))
            qty = int(it.get("quantity"))
        except (TypeError, ValueError):
            errores.append({"index": idx, "error": "item_id/cantidad inválidos"})
            continue

        row = db.execute_query("SELECT name, quantity, price FROM items WHERE id = ?", (item_id,))
        if not row:
            errores.append({"index": idx, "error": "Producto no encontrado"})
            continue

        name, stock, price = row[0]
        if stock < qty:
            errores.append({"index": idx, "error": "Stock insuficiente", "name": name, "requested": qty, "stock": stock})
            continue

        try:
            db.record_product_sale(item_id, qty)
        except Exception as e:
            errores.append({"index": idx, "error": str(e)})
            continue

        resultados.append({
            "item_id": item_id,
            "name": name,
            "quantity": qty,
            "unit_price": price,
            "total": round(price * qty, 2)
        })

    status = 200 if not errores else (207 if resultados else 400)
    return jsonify({"ok": bool(resultados), "items": resultados, "errors": errores}), status
    
@api_bp.route("/sales", methods=["GET"])
def list_sales():
    """Lista las ventas registradas"""
    auth_error = require_auth()
    if auth_error:
        return auth_error
    
    rows = db.execute_query(
        """SELECT s.id, i.barrs_code, i.name, d.price, s.date, d.quantity
           FROM sells s
           JOIN details d ON s.id = d.sell_id
           JOIN items i ON d.item_id = i.id
           ORDER BY s.date DESC
           LIMIT 100"""
    )
    
    sales = [
        {
            "sale_id": row[0],
            "barcode": row[1],
            "product_name": row[2],
            "quantity": row[3],
            "unit_price": row[4],
            "date": row[5]
        }
        for row in rows
    ]
    
    return jsonify(sales), 200
    
@api_bp.route("/items", methods=["GET"])
def search_items():
    """Busca ítems por código de barras o nombre (autocompletar)"""
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