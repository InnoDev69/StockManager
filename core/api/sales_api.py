from miscellaneous import ROLES, PERMS
from flask import Blueprint, jsonify, request, session
from miscellaneous.local_time import localDate
from core.api.notifications_api import notify_user
from core.bd.bdInstance import db
from core.api.auth_utils import require_auth, require_permission
from miscellaneous import logger
from miscellaneous.audit_decorator import audit_action
from core.api.error_handlers import handle_db_error
from core.bd.bdErrors import CreditLimitExceededError, DatabaseError
import sqlite3

sales_api = Blueprint("sales_api", __name__)

ALLOWED_PAYMENT_METHODS = {"Efectivo", "Fiado", "Mixto"}


@sales_api.route("/sales", methods=["POST"])
@require_auth
@require_permission(PERMS.SALES_CREATE)
@audit_action("sale", "create")
def create_sale():
    """
    Registra una nueva venta de un producto por unidad.

    NOTA: este endpoint legacy solo soporta productos por unidad (tabla
    'items'). Para vender productos por peso, o combinar ambos tipos en
    una misma venta, usar POST /sales/bulk.

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
    try:
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

        vendedor_id = session.get("user_id", 0)
        payment_method = data.get("payment_method", "Efectivo")
        db.record_product_sale(item_id, qty, vendedor_id, payment_method)

    except ValueError:
        return jsonify({"error": "Cantidad inválida"}), 400
    except DatabaseError as e:
        return handle_db_error(e, "create_sale")
    except (sqlite3.IntegrityError, sqlite3.OperationalError) as e:
        return handle_db_error(e, "create_sale")
    except Exception as e:
        logger.exception("Unexpected error in create_sale")
        return jsonify({"error": "Error inesperado"}), 500

    return jsonify({
        "message": f"Venta registrada: {name} x{qty}",
        "product": name,
        "quantity": qty,
        "total": price * qty
    }), 201


@sales_api.route("/sales/bulk", methods=["POST"])
@require_auth
@audit_action("sale", "create")
def create_sales_bulk():
    """
    Registra una venta con múltiples productos, por unidad y/o por peso,
    con soporte de fiado/mixto.

    Requiere login: True.

    Request Body (JSON):
        items (array, optional): productos por unidad
          - item_id (int): ID del producto
          - quantity (int): Cantidad a vender
        weight_items (array, optional): productos por peso
          - weight_item_id (int): ID del producto por peso
          - weight (float): gramos vendidos
        payment_method (str, optional): 'Efectivo' (default), 'Fiado' o 'Mixto'
        customer_id (int, requerido si payment_method es Fiado/Mixto)
        amount_paid (float, requerido si payment_method es Mixto)
        force_credit (bool, optional): solo admin/root, permite superar
            el límite de crédito del cliente

        Debe venir al menos uno de 'items' / 'weight_items' no vacío.

    Returns:
        JSON: Resultado de la operación
        - ok (bool): True si la venta fue exitosa
        - sale_id (int): ID de la venta creada
        - items (array): productos por unidad vendidos, con detalle
        - weight_items (array): productos por peso vendidos, con detalle
        - total (float): Total de la venta

    Status Codes:
        201: Venta creada exitosamente
        400: Formato inválido, error en los datos, o límite de crédito superado
        401: No autorizado
        403: force_credit usado sin permisos
    """
    data = request.get_json(silent=True) or {}
    unit_items = data.get("items", [])
    weight_items_in = data.get("weight_items", [])

    if not isinstance(unit_items, list) or not isinstance(weight_items_in, list):
        return jsonify({"error": "Formato inválido: items[] / weight_items[] deben ser listas"}), 400

    if not unit_items and not weight_items_in:
        return jsonify({"error": "La venta necesita al menos un producto"}), 400

    try:
        # ------------------------------------------------------------
        # Parseo de formato (sin tocar la DB todavía)
        # ------------------------------------------------------------
        unit_data = []
        for idx, it in enumerate(unit_items):
            try:
                unit_data.append({
                    "item_id": int(it.get("item_id")),
                    "qty": int(it.get("quantity")),
                })
            except (TypeError, ValueError):
                return jsonify({"error": f"item_id/cantidad inválidos en items[{idx}]"}), 400

        weight_data = []
        for idx, wi in enumerate(weight_items_in):
            try:
                weight_data.append({
                    "weight_item_id": int(wi.get("weight_item_id")),
                    "weight": float(wi.get("weight")),
                })
            except (TypeError, ValueError):
                return jsonify({"error": f"weight_item_id/peso inválidos en weight_items[{idx}]"}), 400
            if weight_data[-1]["weight"] <= 0:
                return jsonify({"error": f"El peso debe ser mayor a 0 en weight_items[{idx}]"}), 400

        # ------------------------------------------------------------
        # Validación + carga en bloque de productos por unidad
        # ------------------------------------------------------------
        validated_units = []
        unit_results = []
        subtotal_units = 0.0

        if unit_data:
            item_ids = [u["item_id"] for u in unit_data]
            placeholders = ",".join("?" * len(item_ids))
            rows = db.execute_query(
                f"SELECT id, name, quantity, price, status FROM items WHERE id IN ({placeholders})",
                tuple(item_ids),
            )
            items_map = {row[0]: row for row in rows}

            unavailable = []
            for u in unit_data:
                row = items_map.get(u["item_id"])
                if row is None:
                    return jsonify({"error": f"Producto con ID {u['item_id']} no encontrado"}), 400

                _, name, stock, price, status = row

                if status == 0:
                    unavailable.append(name)
                    continue

                if stock < u["qty"]:
                    return jsonify({
                        "error": "Stock insuficiente",
                        "product": name,
                        "requested": u["qty"],
                        "available": stock,
                    }), 400

                validated_units.append({"item_id": u["item_id"], "quantity": u["qty"], "price": price})
                subtotal = round(price * u["qty"], 2)
                unit_results.append({
                    "item_id": u["item_id"],
                    "name": name,
                    "quantity": u["qty"],
                    "unit_price": price,
                    "subtotal": subtotal,
                })
                subtotal_units += subtotal

            if unavailable:
                return jsonify({
                    "error": f"Los siguientes productos no están disponibles: {', '.join(unavailable)}"
                }), 400

        # ------------------------------------------------------------
        # Validación + carga en bloque de productos por peso
        # ------------------------------------------------------------
        validated_weights = []
        weight_results = []
        subtotal_weights = 0.0

        if weight_data:
            wi_ids = [w["weight_item_id"] for w in weight_data]
            placeholders = ",".join("?" * len(wi_ids))
            rows = db.execute_query(
                f"SELECT id, name, weight, price, price_per_gram, status FROM weight_items WHERE id IN ({placeholders})",
                tuple(wi_ids),
            )
            weight_items_map = {row[0]: row for row in rows}

            unavailable = []
            for w in weight_data:
                row = weight_items_map.get(w["weight_item_id"])
                if row is None:
                    return jsonify({"error": f"Producto (por peso) con ID {w['weight_item_id']} no encontrado"}), 400

                _, name, stock_weight, price, price_per_gram, status = row

                if status == 0:
                    unavailable.append(name)
                    continue

                if stock_weight < w["weight"]:
                    return jsonify({
                        "error": "Stock insuficiente",
                        "product": name,
                        "requested": w["weight"],
                        "available": stock_weight,
                    }), 400

                # Precio calculado server-side, nunca confiar en un precio
                # mandado por el cliente. price_per_gram es la base de
                # gramos para 'price' (ej: 500 -> price es el precio cada 500g)
                line_price = round((w["weight"] / price_per_gram) * price, 2)

                validated_weights.append({
                    "weight_item_id": w["weight_item_id"],
                    "weight": w["weight"],
                    "price": line_price,
                })
                weight_results.append({
                    "weight_item_id": w["weight_item_id"],
                    "name": name,
                    "weight": w["weight"],
                    "subtotal": line_price,
                })
                subtotal_weights += line_price

            if unavailable:
                return jsonify({
                    "error": f"Los siguientes productos no están disponibles: {', '.join(unavailable)}"
                }), 400

        total = round(subtotal_units + subtotal_weights, 2)

        # ------------------------------------------------------------
        # Pago / crédito
        # ------------------------------------------------------------
        payment_method = data.get("payment_method", "Efectivo")
        if payment_method not in ALLOWED_PAYMENT_METHODS:
            return jsonify({"error": f"payment_method inválido: {payment_method}"}), 400

        customer_id = data.get("customer_id")
        force_credit = data.get("force_credit", False)

        raw_amount_paid = data.get("amount_paid")
        amount_paid = None
        if raw_amount_paid is not None:
            try:
                amount_paid = float(raw_amount_paid)
            except (TypeError, ValueError):
                return jsonify({"error": "amount_paid inválido"}), 400

        vendor_id = session.get("user_id", 0)
        if not vendor_id:
            return jsonify({"error": "Usuario no autenticado"}), 401

        if payment_method in ("Fiado", "Mixto") and not customer_id:
            return jsonify({"error": "Debe seleccionar un cliente para venta fiada"}), 400

        if force_credit and session.get("role") not in (ROLES.ADMIN, ROLES.ROOT):
            return jsonify({"error": "Solo un admin puede forzar el límite de crédito"}), 403

        product_names = [r["name"] for r in unit_results] + [r["name"] for r in weight_results]
        message = f"Venta registrada de los productos {', '.join(product_names)}."

        try:
            sale_id = db.create_mixed_sale(
                date=localDate(),
                vendor_id=vendor_id,
                unit_lines=validated_units,
                weight_lines=validated_weights,
                payment_method=payment_method,
                customer_id=customer_id,
                amount_paid=amount_paid,
                force_credit=force_credit,
            )

            logger.info(
                f"Bulk sale {sale_id} created by {vendor_id} with "
                f"{len(validated_units)} items + {len(validated_weights)} weight_items"
            )

            db.check_and_notify_low_stock(session.get('user_id'))

            db.create_notification(
                user_id=session.get('user_id'),
                title="Venta registrada",
                message=message,
                notification_type='success',
            )
            notify_user(session.get('user_id'))

            return jsonify({
                "ok": True,
                "sale_id": sale_id,
                "items": unit_results,
                "weight_items": weight_results,
                "total": total,
            }), 201

        except CreditLimitExceededError as e:
            logger.warning(f"Credit limit exceeded: {e}")
            return jsonify({"error": str(e), "ok": False, "code": "credit_limit_exceeded"}), 400

        except ValueError as e:
            logger.warning(f"Bulk sale validation: {e}")

            db.create_notification(user_id=session.get('user_id'), title="Error en venta", message="Hubo un error al registrar la venta", notification_type='error')
            notify_user(session.get('user_id'))

            return jsonify({"error": str(e), "ok": False}), 400

        except DatabaseError as e:
            return handle_db_error(e, "bulk_sale")

        except (sqlite3.IntegrityError, sqlite3.OperationalError) as e:
            return handle_db_error(e, "bulk_sale")

        except Exception as e:
            logger.exception("Unexpected error in bulk_sale")

            db.create_notification(user_id=session.get('user_id'), title="Error en venta", message="Hubo un error al registrar la venta", notification_type='error')
            notify_user(session.get('user_id'))

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
        product (str, optional) : Filtro por nombre de producto (unidad o peso)
        vendedor(str, optional) : Filtro por nombre de vendedor
        page    (int, optional) : Pagina, 1-based  (default: 1)
        limit   (int, optional) : Ventas por pagina, max 100  (default: 10)

    Returns:
        JSON:
            data   (list) : Ventas de la pagina actual, cada una con:
                            id, date, products[] (con 'type': 'unit'|'weight'),
                            total_quantity, total, customer_id, customer_name,
                            amount_paid, pending
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
        sell_where.append("""(
            s.id IN (SELECT d2.sell_id FROM details d2 JOIN items i2 ON d2.item_id = i2.id WHERE i2.name LIKE ?)
            OR
            s.id IN (SELECT wd2.sell_id FROM weight_details wd2 JOIN weight_items wi2 ON wd2.weight_item_id = wi2.id WHERE wi2.name LIKE ?)
        )""")
        sell_params.append(f"%{product_q}%")
        sell_params.append(f"%{product_q}%")
    if vendedor_q:
        sell_where.append("s.vendor_id IN (SELECT id FROM users WHERE username LIKE ? OR email LIKE ?)")
        sell_params.append(f"%{vendedor_q}%")
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

        def _new_sale_entry(date, username, vendor_id, payment_method, customer_id, amount_paid, customer_name):
            return {
                "date":           date,
                "products":       [],
                "total_quantity": 0,
                "total":          0.0,
                "vendedor":       username,
                "vendor_id":      vendor_id,
                "payment_method": payment_method,
                "customer_id":    customer_id,
                "customer_name":  customer_name,
                "amount_paid":    amount_paid,
            }

        sales_dict = {}

        # --- Líneas por unidad ---
        unit_detail_query = f"""
            SELECT s.id, s.date, i.name, d.quantity, d.price, u.username, s.vendor_id,
                   s.payment_method, s.customer_id, s.amount_paid, c.name
            FROM sells s
            JOIN details d ON s.id = d.sell_id
            JOIN items  i ON d.item_id = i.id
            LEFT JOIN users u ON s.vendor_id = u.id
            LEFT JOIN customers c ON s.customer_id = c.id
            WHERE s.id IN ({placeholders})
            ORDER BY s.date DESC, s.id DESC
        """
        for sale_id, date, name, quantity, price, username, vendor_id, payment_method, customer_id, amount_paid, customer_name in cur.execute(unit_detail_query, tuple(sale_ids)).fetchall():
            entry = sales_dict.setdefault(
                sale_id,
                {"id": sale_id, **_new_sale_entry(date, username, vendor_id, payment_method, customer_id, amount_paid, customer_name)},
            )
            entry["products"].append({
                "type":     "unit",
                "name":     name,
                "quantity": quantity,
                "price":    float(price),
            })
            entry["total_quantity"] += quantity
            entry["total"] += quantity * float(price)

        # --- Líneas por peso ---
        weight_detail_query = f"""
            SELECT s.id, s.date, wi.name, wd.weight, wd.price, u.username, s.vendor_id,
                   s.payment_method, s.customer_id, s.amount_paid, c.name
            FROM sells s
            JOIN weight_details wd ON s.id = wd.sell_id
            JOIN weight_items wi ON wd.weight_item_id = wi.id
            LEFT JOIN users u ON s.vendor_id = u.id
            LEFT JOIN customers c ON s.customer_id = c.id
            WHERE s.id IN ({placeholders})
            ORDER BY s.date DESC, s.id DESC
        """
        for sale_id, date, name, weight, price, username, vendor_id, payment_method, customer_id, amount_paid, customer_name in cur.execute(weight_detail_query, tuple(sale_ids)).fetchall():
            entry = sales_dict.setdefault(
                sale_id,
                {"id": sale_id, **_new_sale_entry(date, username, vendor_id, payment_method, customer_id, amount_paid, customer_name)},
            )
            entry["products"].append({
                "type":   "weight",
                "name":   name,
                "weight": weight,
                "price":  float(price),
            })
            # 'price' de una línea por peso ya es el total de esa línea
            # (no se multiplica por 'weight', a diferencia de las líneas por unidad).
            entry["total"] += float(price)

    sales = []
    for sid in sale_ids:
        if sid in sales_dict:
            s = sales_dict[sid]
            s["total"] = round(s["total"], 2)
            paid = s["amount_paid"] if s["amount_paid"] is not None else s["total"]
            s["pending"] = round(s["total"] - paid, 2)
            sales.append(s)

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
    Obtiene los detalles de una venta específica (líneas por unidad y por peso).

    Requiere login: True.

    Args:
        sale_id (int): ID de la venta a consultar

    Returns:
        JSON: Detalles completos de la venta
        - id (int): ID de la venta
        - date (str): Fecha y hora de la venta
        - products (array): Lista de productos vendidos
          - type (str): 'unit' | 'weight'
          - name (str): Nombre del producto
          - quantity (int, solo type='unit')
          - weight (float, solo type='weight')
          - price (float)
        - total (float): Total de la venta
        - customer_id, customer_name, amount_paid, pending

    Status Codes:
        200: Venta encontrada
        401: No autorizado
        404: Venta no encontrada
    """
    unit_rows = db.execute_query(
        """
        SELECT s.id, s.date, i.name, d.quantity, d.price, u.username, s.vendor_id,
               s.payment_method, s.customer_id, s.amount_paid, c.name
        FROM sells s
        JOIN details d ON s.id = d.sell_id
        JOIN items i ON d.item_id = i.id
        LEFT JOIN users u ON s.vendor_id = u.id
        LEFT JOIN customers c ON s.customer_id = c.id
        WHERE s.id = ?
        """,
        (sale_id,)
    )

    weight_rows = db.execute_query(
        """
        SELECT s.id, s.date, wi.name, wd.weight, wd.price, u.username, s.vendor_id,
               s.payment_method, s.customer_id, s.amount_paid, c.name
        FROM sells s
        JOIN weight_details wd ON s.id = wd.sell_id
        JOIN weight_items wi ON wd.weight_item_id = wi.id
        LEFT JOIN users u ON s.vendor_id = u.id
        LEFT JOIN customers c ON s.customer_id = c.id
        WHERE s.id = ?
        """,
        (sale_id,)
    )

    if not unit_rows and not weight_rows:
        return jsonify({"error": "Sale not found"}), 404

    header_row = unit_rows[0] if unit_rows else weight_rows[0]
    sale = {
        "id":             header_row[0],
        "date":           header_row[1],
        "products":       [],
        "total":          0.0,
        "vendedor":       header_row[5],
        "vendor_id":      header_row[6],
        "payment_method": header_row[7],
        "customer_id":    header_row[8],
        "amount_paid":    header_row[9],
        "customer_name":  header_row[10],
    }

    for row in unit_rows:
        product = {
            "type":     "unit",
            "name":     row[2],
            "quantity": row[3],
            "price":    float(row[4]),
        }
        sale["products"].append(product)
        sale["total"] += product["quantity"] * product["price"]

    for row in weight_rows:
        product = {
            "type":   "weight",
            "name":   row[2],
            "weight": row[3],
            "price":  float(row[4]),
        }
        sale["products"].append(product)
        sale["total"] += product["price"]

    sale["total"] = round(sale["total"], 2)
    paid = sale["amount_paid"] if sale["amount_paid"] is not None else sale["total"]
    sale["pending"] = round(sale["total"] - paid, 2)

    return jsonify(sale), 200, {'Content-Type': 'application/json'}


@sales_api.route("/sales/<int:sale_id>/edit", methods=["GET"])
@require_permission(PERMS.SALES_EDIT)
def get_sale_for_edit(sale_id):
    """Obtiene detalles de una venta para editar (solo admins)"""
    try:
        sale = db.get_sale_by_id(sale_id)
        if not sale:
            return jsonify({"error": "Venta no encontrada"}), 404
        return jsonify(sale), 200
    except Exception as e:
        logger.exception("Error en get_sale_for_edit")
        return jsonify({"error": "Error interno"}), 500


@sales_api.route("/sales/<int:sale_id>", methods=["PUT"])
@require_permission(PERMS.SALES_EDIT)
@audit_action("sale", "update", "sale_id")
def update_sale(sale_id):
    """Actualiza una venta existente"""
    try:
        data = request.get_json()

        if "items" not in data or not isinstance(data["items"], list):
            return jsonify({"error": "Items inválidos"}), 400

        if not data.get("vendor_id") or not data.get("payment_method"):
            return jsonify({"error": "Faltan campos requeridos"}), 400

        db.update_sale(
            sale_id,
            data["items"],
            data["vendor_id"],
            data["payment_method"],
            user_id=session.get("user_id"),
        )

        db.check_and_notify_low_stock(session.get('user_id'))

        db.create_notification(user_id=session.get('user_id'), title="Venta actualizada", message=f"Venta #{sale_id} ha sido actualizada exitosamente", notification_type='success')
        notify_user(session.get('user_id'))

        return jsonify({"message": "Venta actualizada exitosamente"}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.exception("Error en update_sale")
        return jsonify({"error": "Error interno"}), 500