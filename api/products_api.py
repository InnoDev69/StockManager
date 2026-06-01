from unittest import result

from flask import Blueprint, jsonify, request, session
from api.notifications_api import notify_user
from bd.bdInstance import db
from api.auth_utils import require_auth, require_admin, require_role
from data.validators import ItemValidator, ValidationError
from tools.audit_decorator import audit_action
from tools.logger import logger
from tools.local_time import localDate
from bd.bdErrors import DatabaseError
from api.error_handlers import handle_db_error
import sqlite3
from data.roles import ROLES

ALLOWED_ATTRIBUTE_TYPES = {"text", "number", "date", "bool"}

products_api = Blueprint("products_api", __name__)

@products_api.route("/products_all", methods=["GET"])
@require_auth
def get_all_products():
    """
    Obtiene productos del inventario con paginacion server-side.

    Requiere login: True.

    Query Parameters:
        search      (str, optional) : Busqueda por nombre, codigo de barras o descripcion
        view_mode   (str, optional) : "all" | "in_stock" | "low_stock" | "out_of_stock"
        sort        (str, optional) : Campo de orden: "name" | "stock" | "price"  (default: "name")
        order       (str, optional) : "asc" | "desc"  (default: "asc")
        page        (int, optional) : Numero de pagina, 1-based  (default: 1)
        limit       (int, optional) : Registros por pagina, max 250  (default: 50)

    Returns:
        JSON:
            data   (list) : Productos de la pagina actual
            total  (int)  : Total de registros que coinciden con los filtros
            page   (int)  : Pagina actual
            pages  (int)  : Total de paginas
            limit  (int)  : Registros por pagina usados

    Status Codes:
        200: Exito
        401: No autorizado
    """

    # ── Parametros ────────────────────────────────────────────
    search    = request.args.get("search", "").strip()
    view_mode = request.args.get("view_mode", "all")
    sort      = request.args.get("sort", "name")
    order     = request.args.get("order", "asc").lower()
    page      = max(1, request.args.get("page", 1, type=int))
    limit     = min(250, max(1, request.args.get("limit", 50, type=int)))
    offset    = (page - 1) * limit

    # Whitelist para evitar SQL injection en ORDER BY
    allowed_sort  = {"name", "stock", "price"}
    allowed_order = {"asc", "desc"}
    sort  = sort  if sort  in allowed_sort  else "name"
    order = order if order in allowed_order else "asc"

    # Mapeo campo logico -> columna real
    sort_column = {"name": "name", "stock": "quantity", "price": "price"}[sort]

    # ── Filtros WHERE ─────────────────────────────────────────
    where  = ["1=1"]
    params = []

    if search:
        where.append("(name LIKE ? OR barrs_code LIKE ? OR description LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])

    if view_mode == "in_stock":
        where.append("quantity > min_quantity")
    elif view_mode == "low_stock":
        where.append("quantity > 0 AND quantity <= min_quantity")
    elif view_mode == "out_of_stock":
        where.append("quantity = 0")

    where_clause = " AND ".join(where)

    with db.transaction() as cur:
        # ── COUNT total ───────────────────────────────────────────
        count_query = f"SELECT COUNT(*) FROM items WHERE {where_clause}"
        total = cur.execute(count_query, tuple(params)).fetchone()[0]
        pages = max(1, -(-total // limit))  # ceil division

        # ── Pagina actual ─────────────────────────────────────────
        data_query = f"""
            SELECT id, barrs_code, name, description, quantity, min_quantity, price, status, expiration_date, created_at, updated_at
            FROM items
            WHERE {where_clause}
            ORDER BY {sort_column} {order}
            LIMIT ? OFFSET ?
        """
        rows = cur.execute(data_query, tuple(params) + (limit, offset)).fetchall()

        products = [
            {
                "id":          row[0],
                "barcode":     row[1],
                "name":        row[2],
                "description": row[3],
                "stock":       row[4],
                "min_stock":   row[5],
                "price":       row[6],
                "status":      row[7],
                "expiration_date": row[8],
                "created_at": row[9],
                "updated_at": row[10],
            }
            for row in rows
        ]

    return jsonify({
        "data":  products,
        "total": total,
        "page":  page,
        "pages": pages,
        "limit": limit,
    }), 200
    
@products_api.route("/products", methods=["GET"])
@require_auth
def get_products():
    """
    Obtiene productos activos del inventario con paginacion server-side.

    Requiere login: True.

    Query Parameters:
        search      (str, optional) : Busqueda por nombre o codigo de barras
        view_mode   (str, optional) : "all" | "in_stock" | "out_of_stock"
        sort        (str, optional) : "name" | "stock" | "price"  (default: "name")
        order       (str, optional) : "asc" | "desc"  (default: "asc")
        page        (int, optional) : Pagina, 1-based  (default: 1)
        limit       (int, optional) : Registros por pagina, max 250  (default: 24)

    Returns:
        JSON:
            data   (list) : Productos de la pagina actual
            total  (int)  : Total de registros con los filtros
            page   (int)  : Pagina actual
            pages  (int)  : Total de paginas
            limit  (int)  : Registros por pagina usados

    Status Codes:
        200: Exito
        401: No autorizado
    """

    search    = request.args.get("search", "").strip()
    view_mode = request.args.get("view_mode", "all")
    sort      = request.args.get("sort", "name")
    order     = request.args.get("order", "asc").lower()
    page      = max(1, request.args.get("page", 1, type=int))
    limit     = min(250, max(1, request.args.get("limit", 24, type=int)))
    offset    = (page - 1) * limit

    allowed_sort  = {"name", "stock", "price"}
    allowed_order = {"asc", "desc"}
    sort  = sort  if sort  in allowed_sort  else "name"
    order = order if order in allowed_order else "asc"
    sort_column = {"name": "name", "stock": "quantity", "price": "price"}[sort]

    where  = ["status = 1"]
    params = []

    if search:
        where.append("(name LIKE ? OR barrs_code LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])

    if view_mode == "in_stock":
        where.append("quantity > 0")
    elif view_mode == "out_of_stock":
        where.append("quantity = 0")

    where_clause = " AND ".join(where)

    total = total = db.get_count(
    f"SELECT COUNT(*) FROM items WHERE {where_clause}", tuple(params)
    )
    pages = max(1, -(-total // limit))

    rows = db.get_all_rows(
        f"""
        SELECT id, barrs_code, name, description, quantity, min_quantity, price, status, expiration_date, created_at, updated_at
        FROM items
        WHERE {where_clause}
        ORDER BY {sort_column} {order}
        LIMIT ? OFFSET ?
        """,
        tuple(params) + (limit, offset)
    )

    products = [
        {
            "id":          row[0],
            "barcode":     row[1],
            "name":        row[2],
            "description": row[3],
            "stock":       row[4],
            "min_stock":   row[5],
            "price":       row[6],
            "status":      row[7],
            "expiration_date": row[8],
            "created_at": row[9],
            "updated_at": row[10],
        }
        for row in rows
    ]

    return jsonify({
        "data":  products,
        "total": total,
        "page":  page,
        "pages": pages,
        "limit": limit,
    }), 200

@products_api.route("/products/<int:product_id>", methods=["GET"])
@require_auth
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
        - expiration_date (str): Fecha de expiración
        
    Status Codes:
        200: Producto encontrado
        401: No autorizado
        404: Producto no encontrado
    """
    
    rows = db.execute_query(
        "SELECT id, barrs_code, name, description, quantity, min_quantity, price, expiration_date, created_at, updated_at FROM items WHERE id = ?",
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
        "price": row[6],
        "expiration_date": row[7],
        "created_at": row[8],
        "updated_at": row[9],
    }
    
    return jsonify(product), 200

@products_api.route("/products", methods=["POST"])
@require_role(ROLES.ADMIN, ROLES.ROOT)
@audit_action("product", "create")
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
        expiration_date (str, optional): Fecha de expiración
    
    Returns:
        JSON: {"message": "Producto creado exitosamente"}
    
    Status Codes:
        201: Producto creado exitosamente
        400: Faltan campos requeridos
        401: No autorizado
        403: Permiso denegado (no es admin)
        500: Error en la base de datos
    """
    
    data = request.get_json()
    
    required_fields = ["barcode", "name", "quantity", "min_quantity", "price"]
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Faltan campos requeridos"}), 400
    
    try:
        data = ItemValidator.validate(data.get("barcode", ""), data.get("description", ""), data.get("name", ""), 
                                    data.get("quantity"), data.get("min_quantity"), 
                                    data.get("price"), data.get("expiration_date"), 1)
    except ValidationError as e:
        return jsonify({"error": e.field + ": " + e.message}), 400
    
    try:
        db.add_item(
            data.get("barrs_code", ""),
            data.get("description", ""),
            data["name"],
            data["quantity"],
            data["min_quantity"],
            data["expiration_date"],
            data["price"]
        )
        logger.info(f"Producto '{data['name']}' creado por {session.get('user_id')}")
        db.create_notification(user_id=session.get('user_id'), title="Producto agregado", message=f"El producto '{data['name']}' ha sido agregado al inventario.", notification_type='success')
        notify_user(session.get('user_id'))
        return jsonify({"message": "Producto creado exitosamente"}), 201
    
    except ValidationError as e:
        return jsonify({"error": f"{e.field}: {e.message}"}), 400
    except (sqlite3.IntegrityError, sqlite3.OperationalError, DatabaseError) as e:
        return handle_db_error(e, f"create_product")
    except Exception as e:
        logger.exception("Unexpected error in create_product")
        return jsonify({"error": "Error interno"}), 500

@products_api.route("/products/<int:product_id>", methods=["PUT"])
@require_role(ROLES.ADMIN, ROLES.ROOT)
@audit_action("product", "update", "product_id")
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
        expiration_date (str, optional): Nueva fecha de expiración
        status (int, optional): Nuevo estado (1=activo, 0=deshabilitado)
    
    Returns:
        JSON: {"message": "Producto actualizado"}
    
    Status Codes:
        200: Producto actualizado exitosamente
        400: No hay datos para actualizar
        401: No autorizado
        403: Permiso denegado (no es admin)
    """
    
    data = request.get_json()
    
    updates = []
    params = []
    
    current = db.execute_query(
        "SELECT name, description, quantity, min_quantity, price, expiration_date, status FROM items WHERE id = ?",
        (product_id,)
    )[0]
    
    current_values = {
        "name": current[0],
        "description": current[1],
        "quantity": current[2],
        "min_quantity": current[3],
        "price": current[4],
        "expiration_date": current[5],
        "status": current[6]
    }
        
    field_mapping = {
        "name": "name",
        "description": "description",
        "quantity": "quantity",
        "min_quantity": "min_quantity",
        "price": "price",
        "expiration_date": "expiration_date",
        "status": "status"
    }
    
    for key, db_field in field_mapping.items():
        if key in data and data[key] != current_values.get(key):
            updates.append(f"{db_field} = ?")
            params.append(data[key])
    
    if not updates:
        return jsonify({"error": "No hay datos para actualizar"}), 400
    
    updates.append("updated_at = ?")
    
    params.append(localDate())
    params.append(product_id)
    query = f"UPDATE items SET {', '.join(updates)} WHERE id = ?"
    
    db.execute_query(query, tuple(params), fetch=False)
    
    db.check_and_notify_low_stock(session.get('user_id'))
    
    db.create_notification(user_id=session.get('user_id'), title="Producto actualizado", message=f"El producto '{data.get('name') if data.get('name') else db.get_item_name(product_id)}' ha sido actualizado.", notification_type='success')
    notify_user(session.get('user_id'))
    
    return jsonify({"message": "Producto actualizado"}), 200

@products_api.route("/products/<int:product_id>", methods=["DELETE"])
@require_role(ROLES.ADMIN, ROLES.ROOT)
@audit_action("product", "delete", "product_id")
def delete_product(product_id):
    """
    Deshabilita un producto del inventario.
    
    Requiere login: True.
    Requiere rol: admin.
    
    Args:
        product_id (int): ID del producto a deshabilitar
    
    Returns:
        JSON: {"message": "Producto deshabilitado"}
    
    Status Codes:
        200: Producto deshabilitado exitosamente
        401: No autorizado
        403: Permiso denegado (no es admin)
    """
    
    db.disable_item(product_id)
    db.create_notification(user_id=session.get('user_id'), title="Producto deshabilitado", message=f"El producto ha sido deshabilitado.", notification_type='warning')
    notify_user(session.get('user_id'))
    return jsonify({"message": "Producto deshabilitado"}), 200

@products_api.route("/items", methods=["GET"])
@require_auth
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
    
    query_param = request.args.get("q", "").strip()
    if not query_param:
        return jsonify([]), 200
    
    rows = db.execute_query(
        "SELECT id, barrs_code, name, description, quantity, price FROM items WHERE barrs_code LIKE ? AND status = 1 OR name LIKE ? AND status = 1 LIMIT 10",
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
        
@products_api.route("/products/<int:product_id>/activate", methods=["POST"])
@require_role(ROLES.ADMIN, ROLES.ROOT)
@audit_action("product", "activate", "product_id")
def activate_product(product_id):
    """
    Activa un producto previamente deshabilitado.
    
    Requiere login: True.
    Requiere rol: admin.
    
    Args:
        product_id (int): ID del producto a activar
    
    Returns:
        JSON: {"message": "Producto activado"}
    
    Status Codes:
        200: Producto activado exitosamente
        401: No autorizado
        403: Permiso denegado (no es admin)
    """
    try:
        
        db.activate_item(product_id)
        db.create_notification(user_id=session.get('user_id'), title="Producto activado", message=f"El producto {db.get_item_name(product_id)} ha sido activado.", notification_type='success')
        notify_user(session.get('user_id'))
        
        return jsonify({"message": "Producto activado"}), 200
    
    except Exception as e:
        logger.exception(f"Error al activar producto {product_id}: {str(e)}")
        return jsonify({"error": "Error interno"}), 500