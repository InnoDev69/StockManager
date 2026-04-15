from flask import Blueprint, jsonify, request, session
from api.notifications_api import notify_user
from bd.bdInstance import db
from api.auth_utils import require_auth, require_admin
from data.validators import ItemValidator, ValidationError
from tools.logger import logger
from tools.local_time import localDate
from bd.bdErrors import DatabaseError
from api.error_handlers import handle_db_error
import sqlite3

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

    total = db.execute_query(
        f"SELECT COUNT(*) FROM items WHERE {where_clause}", tuple(params)
    )[0][0]
    pages = max(1, -(-total // limit))

    rows = db.execute_query(
        f"""
        SELECT id, barrs_code, name, description, quantity, min_quantity, price, status, expiration_date, created_at, updated_at
        FROM items
        WHERE {where_clause}
        ORDER BY {sort_column} {order}
        LIMIT ? OFFSET ?
        """,
        tuple(params) + (limit, offset),
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
@require_admin
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
@require_admin
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
    try:
        data = ItemValidator.validate("0", data.get("description", ""), data.get("name", ""), 
                                    data.get("quantity"), data.get("min_quantity"), 
                                    data.get("price"), data.get("expiration_date"), data.get("status"))
    except ValidationError as e:
        return jsonify({"error": e.field + ": " + e.message}), 400
    
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
    
    db.create_notification(user_id=session.get('user_id'), title="Producto actualizado", message=f"El producto '{data.get('name', 'ID ' + str(product_id))}' ha sido actualizado.", notification_type='success')
    notify_user(session.get('user_id'))
    
    return jsonify({"message": "Producto actualizado"}), 200

@products_api.route("/products/<int:product_id>", methods=["DELETE"])
@require_admin
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
    
    if session.get("role") != "admin":
        logger.warning(f"Forbidden disable attempt for product ID {product_id} by user ID {session.get('user_id')}")
        return jsonify({"error": "Permiso denegado"}), 403
    
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

@products_api.route("/products/<int:item_id>/attributes", methods=["POST"])
@require_admin
def create_product_attribute_for_item(item_id):
    """
    POST /api/products/{item_id}/attributes
    
    Crea un NUEVO TIPO de atributo y lo asigna a este producto.
    
    Args:
        item_id (int): ID del producto
    
    Body:
        {
            "name": "Color",
            "data_type": "text",
            "required": false
        }
    
    Returns:
        JSON: {"ok": True, "data": {...}}
    
    Status Codes:
        201: Atributo creado exitosamente
        400: Datos inválidos
        401: No autorizado
        403: Permiso denegado (no es admin)
        404: Producto no encontrado
    """
    
    if session.get("role") != "admin":
        return jsonify({"ok": False, "error": "Permiso denegado"}), 403
    
    if db.get_item_details(item_id) is None:
        return jsonify({"ok": False, "error": "Producto no encontrado"}), 404
    
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    data_type = (data.get("data_type") or "text").strip().lower()
    required = 1 if data.get("required") else 0
    
    if not name:
        return jsonify({"ok": False, "error": "name es obligatorio"}), 400
    
    if data_type not in ALLOWED_ATTRIBUTE_TYPES:
        return jsonify({"ok": False, "error": f"data_type inválido. Usa: {ALLOWED_ATTRIBUTE_TYPES}"}), 400
    
    try:
        code = name.lower().replace(" ", "_")
        
        db.create_item_attribute(name, code, data_type, required)
        
        logger.info(f"Atributo '{name}' creado para producto {item_id} por usuario {session.get('user_id')}")
        
        return jsonify({
            "ok": True,
            "message": "Atributo creado",
            "data": {
                "name": name,
                "code": code,
                "data_type": data_type,
                "required": bool(required)
            }
        }), 201
    
    except Exception as e:
        logger.error(f"Error creando atributo para producto {item_id}: {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 400
    
@products_api.route("/product-attributes", methods=["POST"])
def create_product_attribute():
    """
    POST /api/product-attributes
    
    Crea un TIPO de atributo reutilizable (ej: "Fecha de vencimiento").
    
    Body:
        {
            "name": "Fecha de vencimiento",
            "code": "expiration_date",
            "data_type": "date",
            "required": false
        }
    """
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    code = (data.get("code") or "").strip()
    data_type = (data.get("data_type") or "text").strip().lower()
    required = 1 if data.get("required") else 0

    if not name or not code:
        return jsonify({"ok": False, "error": "name y code obligatorios"}), 400
    if data_type not in ALLOWED_ATTRIBUTE_TYPES:
        return jsonify({"ok": False, "error": f"data_type invalido. Usa: {ALLOWED_ATTRIBUTE_TYPES}"}), 400

    try:
        db.create_item_attribute(name, code, data_type, required)
        return jsonify({"ok": True, "message": "Atributo creado"}), 201
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

@products_api.route("/product-attributes", methods=["GET"])
def list_product_attributes():
    """GET /api/product-attributes"""
    rows = db.list_item_attributes()
    data = [
        {
            "id": r[0],
            "name": r[1],
            "code": r[2],
            "data_type": r[3],
            "required": bool(r[4]),
        }
        for r in rows
    ]
    return jsonify({"ok": True, "data": data}), 200

@products_api.route("/products/<int:item_id>/attributes", methods=["GET"])
@require_auth
def get_product_attributes(item_id):
    """GET /api/products/1/attributes"""
    
    if db.get_item_details(item_id) is None:
        return jsonify({"ok": False, "error": "Producto no encontrado"}), 404
    
    try:
        rows = db.execute_query("""
            SELECT 
                a.id, a.name, a.code, a.data_type, a.required,
                COALESCE(v.value, NULL)
            FROM item_attributes a
            LEFT JOIN item_attribute_values v 
                ON v.item_id = ? AND v.attribute_id = a.id
            ORDER BY a.name
        """, (item_id,))
        
        attributes = [
            {
                "attribute_id": row[0],
                "name": row[1],
                "code": row[2],
                "data_type": row[3],
                "required": bool(row[4]),
                "value": row[5]
            }
            for row in rows
        ]
        
        return jsonify({"ok": True, "data": attributes}), 200
    
    except Exception as e:
        logger.error(f"Error obteniendo atributos: {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 500

@products_api.route("/products/<int:item_id>/attributes", methods=["PUT"])
@require_admin
def upsert_product_attributes(item_id):
    """
    PUT /api/products/1/attributes
    
    Guarda los valores de atributos para este producto.
    
    Body:
        {
            "attributes": [
                { "attribute_id": 1, "value": "2026-12-31" },
                { "attribute_id": 2, "value": "Lote A-19" }
            ]
        }
    """
    payload = request.get_json(silent=True) or {}
    attrs = payload.get("attributes", [])

    if not isinstance(attrs, list):
        return jsonify({"ok": False, "error": "attributes debe ser lista"}), 400

    if db.get_item_details(item_id) is None:
        return jsonify({"ok": False, "error": "Producto no encontrado"}), 404

    try:
        attr_ids_to_validate = [int(a.get("attribute_id")) for a in attrs if a.get("attribute_id")]
        
        if not attr_ids_to_validate:
            return jsonify({"ok": False, "error": "Sin atributos para actualizar"}), 400
        
        placeholders = ",".join("?" * len(attr_ids_to_validate))
        attr_rows = db.execute_query(
            f"""
            SELECT id, name, code, data_type, required, status
            FROM item_attributes
            WHERE id IN ({placeholders})
            """,
            tuple(attr_ids_to_validate)
        )
        
        attr_map = {row[0]: row for row in attr_rows}
        
        for row in attrs:
            attribute_id = int(row.get("attribute_id"))
            value = row.get("value")

            if attribute_id not in attr_map:
                return jsonify({"ok": False, "error": f"Atributo {attribute_id} inexistente"}), 400

            _, name, _, data_type, required, status = attr_map[attribute_id]
            
            if int(required) == 1 and (value is None or str(value).strip() == ""):
                return jsonify({"ok": False, "error": f"Atributo requerido: {name}"}), 400

            if not db._validate_attribute_value(data_type, value):
                return jsonify({"ok": False, "error": f"Valor inválido: {name} debe ser {data_type}"}), 400

            db.set_item_attribute_value(item_id, attribute_id, value)

        return jsonify({"ok": True, "message": "Atributos guardados"}), 200
    
    except Exception as e:
        logger.exception(f"Error en upsert_product_attributes: {e}")
        return jsonify({"ok": False, "error": str(e)}), 400
    
@products_api.route("/attributes/<int:attribute_id>", methods=["DELETE"])
@require_admin
def delete_product_attribute(attribute_id):
    """
    DELETE /api/attributes/{attribute_id}
    
    Elimina un tipo de atributo y todos sus valores asociados.
    
    Args:
        attribute_id (int): ID del atributo a eliminar
    
    Returns:
        JSON: {"ok": True, "message": "Atributo eliminado"}
    
    Status Codes:
        200: Atributo eliminado exitosamente
        400: Atributo no encontrado o error en BD
        401: No autorizado
        403: Permiso denegado (no es admin)
    """
    
    #Verifica si exite
    attr = db.get_item_attribute_by_id(attribute_id)
    if not attr:
        return jsonify({"ok": False, "error": "Atributo no encontrado"}), 404
    
    try:
        db.execute_query(
            "DELETE FROM item_attribute_values WHERE attribute_id = ?",
            (attribute_id,),
            fetch=False
        )
        
        db.execute_query(
            "DELETE FROM item_attributes WHERE id = ?",
            (attribute_id,),
            fetch=False
        )
        
        logger.info(f"Atributo {attribute_id} eliminado por usuario {session.get('user_id')}")
        return jsonify({"ok": True, "message": "Atributo eliminado"}), 200
    
    except Exception as e:
        logger.error(f"Error eliminando atributo {attribute_id}: {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 400
    
@products_api.route("/products/<int:item_id>/attributes", methods=["PUT"])
@require_admin
def update_product_attributes(item_id):
    """
    PUT /api/products/{item_id}/attributes
    """
    
    if db.get_item_details(item_id) is None:
        return jsonify({"ok": False, "error": "Producto no encontrado"}), 404
    
    data = request.get_json(silent=True) or {}
    attributes = data.get("attributes", [])
    
    if not isinstance(attributes, list):
        return jsonify({"ok": False, "error": "attributes debe ser un array"}), 400
    
    try:
        attr_ids = [a.get("attribute_id") for a in attributes if a.get("attribute_id")]
        attr_ids = list(set(attr_ids))
        
        if not attr_ids:
            db.execute_query(
                "DELETE FROM item_attribute_values WHERE item_id = ?",
                (item_id,),
                fetch=False
            )
            return jsonify({"ok": True, "message": "Atributos limpiados"}), 200
        
        placeholders = ",".join("?" * len(attr_ids))
        attr_defs = db.execute_query(
            f"""
            SELECT id, name, data_type, required
            FROM item_attributes
            WHERE id IN ({placeholders})
            """,
            tuple(attr_ids)
        )
        
        attr_map = {row[0]: row for row in attr_defs}
        
        with db.transaction() as cur:
            cur.execute(
                "DELETE FROM item_attribute_values WHERE item_id = ?",
                (item_id,)
            )
            
            for attr in attributes:
                attr_id = attr.get("attribute_id")
                value = attr.get("value")
                
                if attr_id is None or attr_id not in attr_map:
                    continue
                
                attr_id_int, name, data_type, required = attr_map[attr_id]
                
                if int(required) == 1 and (value is None or str(value).strip() == ""):
                    return jsonify({
                        "ok": False, 
                        "error": f"Atributo obligatorio: {name}"
                    }), 400
                
                if value is not None and str(value).strip():
                    cur.execute(
                        """
                        INSERT INTO item_attribute_values (item_id, attribute_id, value)
                        VALUES (?, ?, ?)
                        """,
                        (item_id, attr_id, str(value).strip())
                    )
        
        logger.info(f"Atributos actualizados para producto {item_id}")
        return jsonify({
            "ok": True, 
            "message": "Atributos actualizados"
        }), 200
    
    except Exception as e:
        logger.exception(f"Error actualizando atributos: {e}")
        return jsonify({
            "ok": False, 
            "error": str(e)
        }), 400
        
@products_api.route("/products/<int:product_id>/activate", methods=["POST"])
@require_admin
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
        if session.get("role") != "admin":
            return jsonify({"error": "Permiso denegado"}), 403
        
        db.activate_item(product_id)
        db.create_notification(user_id=session.get('user_id'), title="Producto activado", message=f"El producto {db.get_item_name(product_id)} ha sido activado.", notification_type='success')
        notify_user(session.get('user_id'))
        
        return jsonify({"message": "Producto activado"}), 200
    
    except Exception as e:
        logger.exception(f"Error al activar producto {product_id}: {str(e)}")
        return jsonify({"error": "Error interno"}), 500