from flask import Blueprint, jsonify, request, session
from bd.bdInstance import db
from api.auth_utils import require_auth
from tools.logger import logger
from api.error_handlers import handle_db_error
from bd.bdErrors import DatabaseError
import sqlite3

sales_api = Blueprint("sales_api", __name__)

@sales_api.route("/sales", methods=["POST"])
@require_auth
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
    
    vendedor = session.get("username", "unknown")
    payment_method = data.get("payment_method", "Efectivo")
    db.record_product_sale(item_id, qty, vendedor, payment_method)
    
    return jsonify({
        "message": f"Venta registrada: {name} x{qty}",
        "product": name,
        "quantity": qty,
        "total": price * qty
    }), 201
    
@sales_api.route("/sales/bulk", methods=["POST"])
@require_auth
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

    data = request.get_json(silent=True) or {}
    items = data.get("items", [])
    if not isinstance(items, list) or not items:
        return jsonify({"error": "Formato inválido: items[] requerido"}), 400

    try:
        item_data = []
        item_ids = []
        for idx, it in enumerate(items):
            try:
                item_id = int(it.get("item_id"))
                qty = int(it.get("quantity"))
                item_ids.append(item_id)
                item_data.append({"item_id": item_id, "qty": qty, "idx": idx})
            except (TypeError, ValueError):
                return jsonify({"error": f"item_id/cantidad inválidos en índice {idx}"}), 400
        
        if not item_ids:
            return jsonify({"error": "No hay items para validar"}), 400
        
        placeholders = ",".join("?" * len(item_ids))
        rows = db.execute_query(
            f"SELECT id, name, quantity, price FROM items WHERE id IN ({placeholders})",
            tuple(item_ids)
        )
        
        items_map = {row[0]: row for row in rows}
        
        validated_items = []
        resultados = []
        total = 0
        
        for item_info in item_data:
            item_id = item_info["item_id"]
            qty = item_info["qty"]
            idx = item_info["idx"]
            
            if item_id not in items_map:
                return jsonify({"error": f"Producto con ID {item_id} no encontrado"}), 400
            
            _, name, stock, price = items_map[item_id]
            
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
        
        vendedor = session.get("username", "unknown")
        payment_method = data.get("payment_method", "Efectivo")
        
        try:
            sale_id = db.record_bulk_sale(validated_items, vendedor, payment_method)
            logger.info(f"Bulk sale {sale_id} created by {vendedor} with {len(validated_items)} items")
            return jsonify({
                "ok": True,
                "sale_id": sale_id,
                "items": resultados,
                "total": round(total, 2)
            }), 201
        
        except ValueError as e:
            logger.warning(f"Bulk sale validation: {e}")
            return jsonify({"error": str(e), "ok": False}), 400
        
        except DatabaseError as e:
            return handle_db_error(e, "bulk_sale")
        
        except (sqlite3.IntegrityError, sqlite3.OperationalError) as e:
            return handle_db_error(e, "bulk_sale")
        
        except Exception as e:
            logger.exception("Unexpected error in bulk_sale")
            return jsonify({"error": "Error inesperado", "ok": False}), 500
    
    except Exception as e:
        logger.exception("Bulk sale error")
        return jsonify({"error": "Error interno", "ok": False}), 500

@sales_api.route("/sales", methods=["GET"])
@require_auth
def list_sales():
    """
    Lista ventas con paginacion server-side.

    Requiere login: True.

    Query Parameters:
        from    (str, optional) : Fecha inicial YYYY-MM-DD
        to      (str, optional) : Fecha final   YYYY-MM-DD
        product (str, optional) : Filtro por nombre de producto
        vendedor(str, optional) : Filtro por nombre de vendedor
        page    (int, optional) : Pagina, 1-based  (default: 1)
        limit   (int, optional) : Ventas por pagina, max 100  (default: 10)

    Returns:
        JSON:
            data   (list) : Ventas de la pagina actual, cada una con:
                            id, date, products[], total_quantity, total
            total  (int)  : Total de ventas que coinciden con los filtros
            page   (int)  : Pagina actual
            pages  (int)  : Total de paginas
            limit  (int)  : Registros por pagina usados

    Status Codes:
        200: Exito
        401: No autorizado
    """

    date_from   = request.args.get("from")
    date_to     = request.args.get("to")
    product_q   = request.args.get("product", "").strip()
    vendedor_q = request.args.get("vendedor", "").strip()
    page        = max(1, request.args.get("page", 1, type=int))
    limit       = min(100, max(1, request.args.get("limit", 10, type=int)))
    offset      = (page - 1) * limit

    sell_where  = ["1=1"]
    sell_params = []

    if date_from:
        sell_where.append("DATE(s.date) >= ?")
        sell_params.append(date_from)
    if date_to:
        sell_where.append("DATE(s.date) <= ?")
        sell_params.append(date_to)
    if product_q:
        sell_where.append("s.id IN (SELECT d2.sell_id FROM details d2 JOIN items i2 ON d2.item_id = i2.id WHERE i2.name LIKE ?)")
        sell_params.append(f"%{product_q}%")
    if vendedor_q:
        sell_where.append("s.vendedor LIKE ?")
        sell_params.append(f"%{vendedor_q}%")

    sell_where_clause = " AND ".join(sell_where)

    count_query = f"""
        SELECT COUNT(DISTINCT s.id)
        FROM sells s
        WHERE {sell_where_clause}
    """
    with db.transaction() as cur:
        total = cur.execute(count_query, tuple(sell_params)).fetchone()[0]
        pages = max(1, -(-total // limit))

        ids_query = f"""
            SELECT DISTINCT s.id
            FROM sells s
            WHERE {sell_where_clause}
            ORDER BY s.date DESC, s.id DESC
            LIMIT ? OFFSET ?
        """
        id_rows = cur.execute(ids_query, tuple(sell_params) + (limit, offset)).fetchall()

        if not id_rows:
            return jsonify({
                "data":  [],
                "total": total,
                "page":  page,
                "pages": pages,
                "limit": limit,
            }), 200

        sale_ids = [row[0] for row in id_rows]

        placeholders = ",".join("?" * len(sale_ids))
        detail_query = f"""
            SELECT s.id, s.date, i.name, d.quantity, d.price, s.vendedor, s.payment_method
            FROM sells s
            JOIN details d ON s.id = d.sell_id
            JOIN items  i ON d.item_id = i.id
            WHERE s.id IN ({placeholders})
            ORDER BY s.date DESC, s.id DESC
        """
        rows = cur.execute(detail_query, tuple(sale_ids)).fetchall()

        sales_dict = {}
        for sale_id, date, name, quantity, price, vendedor, payment_method in rows:
            if sale_id not in sales_dict:
                sales_dict[sale_id] = {
                    "id":             sale_id,
                    "date":           date,
                    "products":       [],
                    "total_quantity": 0,
                    "total":          0.0,
                    "vendedor":       vendedor,
                    "payment_method": payment_method,
                }
            sales_dict[sale_id]["products"].append({
                "name":     name,
                "quantity": quantity,
                "price":    float(price),
            })
            sales_dict[sale_id]["total_quantity"] += quantity
            sales_dict[sale_id]["total"]          += quantity * float(price)

    sales = []
    for sid in sale_ids:
        if sid in sales_dict:
            sales_dict[sid]["total"] = round(sales_dict[sid]["total"], 2)
            sales.append(sales_dict[sid])

    return jsonify({
        "data":  sales,
        "total": total,
        "page":  page,
        "pages": pages,
        "limit": limit,
    }), 200
    
@sales_api.route("/sales/<int:sale_id>", methods=["GET"])
@require_auth
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
    
    sale_data = db.execute_query(
        """
        SELECT s.id, s.date, i.name, d.quantity, d.price, s.vendedor, s.payment_method
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
        "id":             sale_data[0][0],
        "date":           sale_data[0][1],
        "products":       [],
        "total":          0.0,
        "vendedor":       sale_data[0][5],
        "payment_method": sale_data[0][6],
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