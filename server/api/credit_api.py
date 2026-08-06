from flask import Blueprint, jsonify, request, session
from miscellaneous import ROLES
from miscellaneous.audit_decorator import audit_action
from server.bd.bdInstance import db
from server.api.auth_utils import require_auth, require_role
from server.api.error_handlers import handle_db_error
from server.bd.bdErrors import DatabaseError, InsufficientBalanceError

credit_api = Blueprint("credit_api", __name__)


@credit_api.route("/customers", methods=["POST"])
@require_auth
@audit_action("customer", "create")
def create_customer():
    """
    Crea un cliente para cuenta corriente.

    Request Body (JSON):
        name (str): Nombre del cliente (requerido)
        phone (str, optional)
        credit_limit (float, optional)

    Status Codes:
        201: Cliente creado
        400: Falta el nombre
    """
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "El nombre es requerido"}), 400

    try:
        customer_id = db.create_customer(
            name=name,
            phone=data.get("phone"),
            credit_limit=data.get("credit_limit"),
        )
        return jsonify({"ok": True, "customer_id": customer_id}), 201
    except DatabaseError as e:
        return handle_db_error(e, "create_customer")


@credit_api.route("/customers", methods=["GET"])
@require_auth
def list_customers():
    """
    Lista clientes activos con su saldo actual. Soporta búsqueda por nombre.

    Query Parameters:
        q (str, optional): Filtro por nombre
    """
    search = request.args.get("q", "").strip() or None
    rows = db.list_customers_with_balance(search=search)
    return jsonify({
        "data": [
            {
                "id": r[0], "name": r[1], "phone": r[2],
                "credit_limit": r[3], "status": r[4], "balance": r[5],
            }
            for r in rows
        ]
    }), 200


@credit_api.route("/customers/<int:customer_id>/balance", methods=["GET"])
@require_auth
def get_customer_balance(customer_id):
    """Retorna el saldo pendiente actual del cliente, junto a sus datos."""
    customer = db.get_customer(customer_id)
    if not customer:
        return jsonify({"error": "Cliente no encontrado"}), 404

    balance = db.get_customer_balance(customer_id)
    return jsonify({
        "customer_id": customer_id,
        "name": customer[1],
        "phone": customer[2],
        "credit_limit": customer[3],
        "balance": balance,
    }), 200


@credit_api.route("/customers/<int:customer_id>/movements", methods=["GET"])
@require_auth
def get_customer_movements(customer_id):
    """Historial de movimientos de cuenta corriente del cliente."""
    if not db.get_customer(customer_id):
        return jsonify({"error": "Cliente no encontrado"}), 404

    limit = min(200, max(1, request.args.get("limit", 50, type=int)))
    rows = db.get_customer_movements(customer_id, limit=limit)
    return jsonify({
        "data": [
            {
                "id": r[0], "sell_id": r[1], "type": r[2],
                "amount": r[3], "date": r[4], "user_id": r[5], "note": r[6],
            }
            for r in rows
        ]
    }), 200


@credit_api.route("/customers/<int:customer_id>/payments", methods=["POST"])
@require_auth
@audit_action("customer_payment", "create")
def register_payment(customer_id):
    """
    Registra un abono a la cuenta corriente del cliente.

    Request Body (JSON):
        amount (float): Monto abonado (requerido, > 0)
        note (str, optional)

    Status Codes:
        201: Pago registrado
        400: Monto inválido o mayor al saldo pendiente
        404: Cliente no encontrado
    """
    if not db.get_customer(customer_id):
        return jsonify({"error": "Cliente no encontrado"}), 404

    data = request.get_json(silent=True) or {}
    try:
        amount = float(data.get("amount"))
    except (TypeError, ValueError):
        return jsonify({"error": "Monto inválido"}), 400

    vendor_id = session.get("user_id", 0)
    try:
        movement_id = db.register_payment(customer_id, amount, vendor_id, note=data.get("note"))
        return jsonify({"ok": True, "movement_id": movement_id}), 201
    except InsufficientBalanceError as e:
        return jsonify({"error": str(e), "ok": False}), 400
    except DatabaseError as e:
        return handle_db_error(e, "register_payment")


@credit_api.route("/customers/<int:customer_id>/adjustments", methods=["POST"])
@require_role(ROLES.ADMIN, ROLES.ROOT)
@audit_action("customer_adjustment", "create")
def register_adjustment(customer_id):
    """
    Registra un ajuste manual en la cuenta corriente (solo admins).

    Request Body (JSON):
        amount (float): Monto del ajuste (puede ser negativo)
        note (str): Justificación, obligatoria

    Status Codes:
        201: Ajuste registrado
        400: Datos inválidos
    """
    if not db.get_customer(customer_id):
        return jsonify({"error": "Cliente no encontrado"}), 404

    data = request.get_json(silent=True) or {}
    note = (data.get("note") or "").strip()
    try:
        amount = float(data.get("amount"))
    except (TypeError, ValueError):
        return jsonify({"error": "Monto inválido"}), 400

    if not note:
        return jsonify({"error": "El ajuste requiere una nota"}), 400

    vendor_id = session.get("user_id", 0)
    try:
        movement_id = db.register_adjustment(customer_id, amount, vendor_id, note)
        return jsonify({"ok": True, "movement_id": movement_id}), 201
    except DatabaseError as e:
        return handle_db_error(e, "register_adjustment")


@credit_api.route("/customers/<int:customer_id>", methods=["POST"])
@require_auth
@audit_action("customer", "update")
def update_customer(customer_id):
    """
    Actualiza los datos de un cliente.

    Request Body (JSON):
        name (str, optional)
        phone (str, optional)
        credit_limit (float|null, optional): si la clave está presente en el
            JSON (incluso como null), se actualiza el límite; si la clave no
            viene, el límite actual no se toca.

    Status Codes:
        200: Cliente actualizado
        404: Cliente no encontrado
    """
    if not db.get_customer(customer_id):
        return jsonify({"error": "Cliente no encontrado"}), 404

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip() or None
    phone = (data.get("phone") or "").strip() or None

    credit_limit_provided = "credit_limit" in data
    raw_limit = data.get("credit_limit")
    credit_limit = None
    if credit_limit_provided and raw_limit not in (None, ""):
        try:
            credit_limit = float(raw_limit)
        except (TypeError, ValueError):
            return jsonify({"error": "credit_limit inválido"}), 400

    try:
        db.update_customer(
            customer_id,
            name=name,
            phone=phone,
            credit_limit=credit_limit,
            update_credit_limit=credit_limit_provided,
        )
        return jsonify({"ok": True}), 200
    except DatabaseError as e:
        return handle_db_error(e, "update_customer")