import secrets
import sqlite3
from flask import Blueprint, jsonify, request, session
from werkzeug.security import generate_password_hash
from api.error_handlers import handle_db_error
from bd.bdInstance import db
from api.auth_utils import require_auth, require_admin
from data.validators import UserValidator, ValidationError
from tools.logger import logger
from tools.email import email_sender

users_api = Blueprint("users_api", __name__)

def generate_reset_code():
    """Genera un código de recuperación aleatorio de 6 dígitos."""
    import secrets
    return f"{secrets.randbelow(10**6):06d}"

@users_api.route("/users", methods=["GET"])
@require_admin
def get_users():
    """Lista todos los usuarios con paginación."""

    search = request.args.get("search", "").strip()
    page   = max(1, request.args.get("page", 1, type=int))
    limit  = min(100, max(1, request.args.get("limit", 10, type=int)))
    offset = (page - 1) * limit

    where  = ["1=1"]
    params = []

    if search:
        where.append("(username LIKE ? OR email LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])

    where_clause = " AND ".join(where)

    total = db.execute_query(
        f"SELECT COUNT(*) FROM users WHERE {where_clause}", tuple(params)
    )[0][0]
    pages = max(1, -(-total // limit))

    rows = db.execute_query(
        f"""
        SELECT id, username, email, role, status, created_at
        FROM users
        WHERE {where_clause}
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
        """,
        tuple(params) + (limit, offset)
    )

    users_list = [
        {
            "id":         row[0],
            "username":   row[1],
            "email":      row[2],
            "role":       row[3],
            "status":     row[4],
            "created_at": row[5],
        }
        for row in rows
    ]

    return jsonify({
        "data":  users_list,
        "total": total,
        "page":  page,
        "pages": pages,
        "limit": limit,
    }), 200


@users_api.route("/users/<int:user_id>", methods=["GET"])
@require_admin
def get_user(user_id):
    """Obtiene un usuario específico."""

    rows = db.execute_query(
        "SELECT id, username, email, role, status, created_at FROM users WHERE id = ?",
        (user_id,)
    )
    if not rows:
        return jsonify({"error": "Usuario no encontrado"}), 404

    r = rows[0]
    return jsonify({
        "id":         r[0],
        "username":   r[1],
        "email":      r[2],
        "role":       r[3],
        "status":     r[4],
        "created_at": r[5],
    }), 200


@users_api.route("/users", methods=["POST"])
@require_admin
def create_user():
    """Crea un nuevo usuario."""

    data = request.get_json()
    required = ["username", "email", "password", "role"]
    if not all(f in data for f in required):
        return jsonify({"error": "Faltan campos requeridos"}), 400

    try:
        UserValidator.validate_email(data["email"])
    except Exception:
        return jsonify({"error": "Formato de correo inválido"}), 400

    existing = db.get_user_by_email(data["email"].strip())
    if existing:
        return jsonify({"error": "El correo ya está registrado"}), 409

    hashed = generate_password_hash(data["password"])
    try:
        UserValidator.validate_email(data["email"])
    except ValidationError as e:
        return jsonify({"error": f"{e.field}: {e.message}"}), 400
    
    try:
        db.execute_query("INSERT INTO users ...", fetch=False)
        logger.info(f"User {data['username']} created by admin {session.get('user_id')}")
        return jsonify({"message": "Usuario creado exitosamente"}), 201
    
    except sqlite3.IntegrityError as e:
        if "email" in str(e):
            return jsonify({"error": "Este correo ya está registrado"}), 409
        if "username" in str(e):
            return jsonify({"error": "Este usuario ya existe"}), 409
        return handle_db_error(e, "create_user")
    
    except Exception as e:
        return handle_db_error(e, "create_user")

@users_api.route("/users/<int:user_id>", methods=["PUT"])
@require_admin
def update_user(user_id):
    """Actualiza un usuario existente."""

    data = request.get_json()
    updates = []
    params  = []

    if "username" in data:
        updates.append("username = ?")
        params.append(data["username"].strip())
    if "email" in data:
        updates.append("email = ?")
        params.append(data["email"].strip())
    if "role" in data:
        updates.append("role = ?")
        params.append(data["role"])
    if "status" in data:
        updates.append("status = ?")
        params.append(int(data["status"]))
    if "password" in data and data["password"]:
        updates.append("password = ?")
        params.append(generate_password_hash(data["password"]))

    if not updates:
        return jsonify({"error": "No hay datos para actualizar"}), 400

    params.append(user_id)
    db.execute_query(
        f"UPDATE users SET {', '.join(updates)} WHERE id = ?",
        tuple(params),
        fetch=False
    )
    logger.info(f"Usuario ID {user_id} actualizado por admin ID {session.get('user_id')}")
    return jsonify({"message": "Usuario actualizado"}), 200


@users_api.route("/users/<int:user_id>", methods=["DELETE"])
@require_admin
def delete_user(user_id):
    """Deshabilita un usuario (baja lógica)."""

    if user_id == session.get("user_id"):
        return jsonify({"error": "No puedes darte de baja a ti mismo"}), 400

    db.execute_query(
        "UPDATE users SET status = 0 WHERE id = ?",
        (user_id,),
        fetch=False
    )
    logger.info(f"Usuario ID {user_id} dado de baja por admin ID {session.get('user_id')}")
    return jsonify({"message": "Usuario dado de baja"}), 200


@users_api.route("/users/<int:user_id>/activity", methods=["GET"])
@require_admin
def get_user_activity(user_id):
    """Obtiene los movimientos/ventas de un usuario."""

    page   = max(1, request.args.get("page", 1, type=int))
    limit  = min(100, max(1, request.args.get("limit", 10, type=int)))
    offset = (page - 1) * limit

    user_rows = db.execute_query(
        "SELECT username FROM users WHERE id = ?", (user_id,)
    )
    if not user_rows:
        return jsonify({"error": "Usuario no encontrado"}), 404

    username = user_rows[0][0]

    total = db.execute_query(
        "SELECT COUNT(*) FROM sells WHERE vendedor = ?", (username,)
    )[0][0]
    pages = max(1, -(-total // limit))

    rows = db.execute_query(
        """
        SELECT s.id, s.date, s.payment_method,
               COUNT(d.id) AS items,
               SUM(d.quantity * d.price) AS total
        FROM sells s
        JOIN details d ON s.id = d.sell_id
        WHERE s.vendedor = ?
        GROUP BY s.id
        ORDER BY s.date DESC
        LIMIT ? OFFSET ?
        """,
        (username, limit, offset)
    )

    activity = [
        {
            "sale_id":        r[0],
            "date":           r[1],
            "payment_method": r[2],
            "items":          int(r[3]),
            "total":          round(float(r[4]), 2),
        }
        for r in rows
    ]

    return jsonify({
        "username": username,
        "data":     activity,
        "total":    total,
        "page":     page,
        "pages":    pages,
        "limit":    limit,
    }), 200
    
@users_api.route("/users/reset-password", methods=["POST"])
def restore_password():
    """
    Endpoint para restaurar la contraseña de un usuario.
    
    Requiere login: False.
    
    Request Body (JSON):
        email (str): Correo electrónico del usuario
    
    Returns:
        JSON: {"message": "Codigo enviado al correo"}
    
    Status Codes:
        200: Codigo enviado exitosamente
        400: Faltan campos requeridos o formato inválido
        404: Usuario no encontrado
    
    Example Request:
        POST /users/reset-password
        {
            "email": "usuario@ejemplo.com"
        }
    """
    
    data = request.get_json()
    
    logger.info(f"Password reset requested for email: {data.get('email', 'N/A')}")
    
    if "email" not in data:
        return jsonify({"error": "Faltan campos requeridos"}), 400
    
    email = data["email"].strip()
    
    if not UserValidator.validate_email(email):
        return jsonify({"error": "Formato de correo inválido"}), 400
    
    user = db.get_user_by_email(email)
    
    if not user:
        return jsonify({"error": "Usuario no encontrado"}), 404
    
    reset_code = generate_reset_code()
    db.save_reset_code(email, reset_code)
    
    email_sender.send_email(
        email,
        subject="Código de recuperación de contraseña",
        body=f"Tu código de recuperación es: {reset_code}. Este código es válido por 15 minutos."
    )
    
    return jsonify({"message": "Codigo enviado al correo"}), 200

@users_api.route("/users/validate-code", methods=["POST"])
def verify_code():
    """
    Endpoint para verificar el código de recuperación de contraseña.
    
    Requiere login: False.
    
    Request Body (JSON):
        email (str): Correo electrónico del usuario
        code (str): Código de recuperación enviado al correo
    
    Returns:
        JSON: {"message": "Código verificado, puedes restablecer tu contraseña"}
    
    Status Codes:
        200: Código verificado exitosamente
        400: Faltan campos requeridos o formato inválido
        404: Usuario no encontrado
        401: Código inválido o expirado
    
    Example Request:
        POST /users/validate-code
        {
            "email": "usuario@ejemplo.com",
            "code": "123456"
        }
    """
    data = request.get_json()
    
    if "email" not in data or "code" not in data:
        return jsonify({"error": "Faltan campos requeridos"}), 400
    
    code_status = db.verify_code(email=data.get("email", ""), code=data.get("code", ""))

    if not code_status:
        return jsonify({"error": "Código inválido o expirado"}), 401
    
    return jsonify({"message": "Código verificado, puedes restablecer tu contraseña"}), 200

@users_api.route("/users/reset-password/change-password", methods=["POST"])
def change_password():
    """
    Endpoint para cambiar la contraseña después de verificar el código de recuperación.
    
    Requiere login: False.
    
    Request Body (JSON):
        email (str): Correo electrónico del usuario
        new_password (str): Nueva contraseña a establecer
    
    Returns:
        JSON: {"message": "Contraseña restablecida exitosamente"}
    
    Status Codes:
        200: Contraseña cambiada exitosamente
        400: Faltan campos requeridos o formato inválido
        404: Usuario no encontrado
        401: No autorizado (si el código no fue verificado)
    
    Example Request:
        POST /users/reset-password/change-password
        {
            "email": "usuario@ejemplo.com",
            "code": "123456",
            "new_password": "nueva_contraseña_segura"
        }
    """
    data = request.get_json()
    
    if not db.verify_code(email=data.get("email", ""), code=data.get("code", "")):
        return jsonify({"error": "Código no verificado o expirado"}), 401
    
    if "email" not in data or "new_password" not in data:
        return jsonify({"error": "Faltan campos requeridos"}), 400
    
    email = data["email"].strip()
    new_password = data["new_password"].strip()
    
    if not UserValidator.validate_email(email):
        return jsonify({"error": "Formato de correo inválido"}), 400
    
    user = db.get_user_by_email(email)
    
    if not user:
        return jsonify({"error": "Usuario no encontrado"}), 404
    
    hashed = generate_password_hash(new_password)
    db.update_user_password(email, hashed)
    
    db.delete_reset_code(email=data["email"])
    
    return jsonify({"message": "Contraseña restablecida exitosamente"}), 200
