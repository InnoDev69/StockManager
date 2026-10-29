import sqlite3
from miscellaneous import Var
from flask import Blueprint, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash
from miscellaneous.permissions import PERMS
from core.api.error_handlers import handle_db_error
from core.bd.bdInstance import db
from core.bd.bdErrors import DatabaseError
from core.api.auth_utils import require_auth, require_permission
from miscellaneous.validators import RoleValidator, UserValidator, ValidationError
from miscellaneous import logger, email_sender
from miscellaneous.audit_decorator import audit_action
from miscellaneous import ROLES

users_api = Blueprint("users_api", __name__)

def _email_valido(email):
    """
    True si el email es válido. UserValidator.validate_email lanza ValidationError cuando
    es inválido (así lo usan create_user y api_register); también se contempla que
    devuelva False, para no depender de cuál de los dos estilos use.
    """
    try:
        return UserValidator.validate_email(email) is not False
    except ValidationError:
        return False


def generate_reset_code():
    """Genera un código de recuperación aleatorio de 6 dígitos."""
    import secrets
    return f"{secrets.randbelow(10**6):06d}"

@users_api.route("/users", methods=["GET"])
@require_permission(PERMS.USERS_MANAGE)
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
@require_permission(PERMS.USERS_MANAGE)
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
@require_permission(PERMS.USERS_MANAGE)
@audit_action("user", "create")
def create_user():
    """Crea un nuevo usuario."""

    data = request.get_json()
    required = ["username", "email", "password", "role"]
    if not all(f in data for f in required):
        return jsonify({"error": "Faltan campos requeridos"}), 400

    existing = db.get_user_by_email(data["email"].strip())
    if existing:
        return jsonify({"error": "El correo ya está registrado"}), 409

    hashed = generate_password_hash(data["password"])
    try:
        UserValidator.validate_email(data["email"])
    except ValidationError as e:
        return jsonify({"error": f"{e.field}: {e.message}"}), 400
    
    try:
        data["role"] = RoleValidator.validate_name(data["role"])
    except ValidationError as e:
        return jsonify({"error": e.message}), 400
    
    if data["role"] == ROLES.ROOT and session.get("role") != ROLES.ROOT:
        logger.warning(f"Intento de crear un usuario root por admin ID {session.get('user_id')}")
        return jsonify({"error": "Solo un usuario root puede crear usuarios root"}), 403
    
    username = data["username"].strip()
    if db.get_single_row("SELECT id FROM users WHERE username = ?", (username,)):
        return jsonify({"error": "Este usuario ya existe"}), 409

    try:
        db.add_user(
            username=username,
            email=data["email"].strip(),
            password=hashed,
            role=data["role"],
            status=1,
            application=Var.USER_APPLICATION_ACCEPTED
        )
        logger.info(f"User {data['username']} created by admin {session.get('user_id')}")
        return jsonify({"message": "Usuario creado exitosamente"}), 201
    
    except Exception as e:
        # Respaldo ante una carrera entre el chequeo de arriba y el INSERT: db._cursor()
        # convierte todo sqlite3.Error en DatabaseError, no en sqlite3.IntegrityError.
        msg = str(e).lower()
        if isinstance(e, (sqlite3.IntegrityError, DatabaseError)) and "unique" in msg:
            if "email" in msg:
                return jsonify({"error": "Este correo ya está registrado"}), 409
            if "username" in msg:
                return jsonify({"error": "Este usuario ya existe"}), 409
        return handle_db_error(e, "create_user")

@users_api.route("/users/<int:target_user_id>", methods=["PUT"])
@require_permission(PERMS.USERS_MANAGE)
@audit_action("user", "update", "target_user_id")
def update_user(target_user_id):
    """Actualiza un usuario existente (solo si hay cambios reales)."""

    current_user = db.execute_query(
        "SELECT username, email, role, status FROM users WHERE id = ?",
        (target_user_id,)
    )
    if not current_user:
        return jsonify({"error": "Usuario no encontrado"}), 404
    
    current_username, current_email, current_role, current_status = current_user[0]

    # Solo un root puede modificar a otro root (cambiarle la contraseña, el estado, el rol...).
    soy_root = session.get("role") == ROLES.ROOT
    if current_role == ROLES.ROOT and not soy_root:
        logger.warning(f"Intento de modificar al usuario root ID {target_user_id} por admin ID {session.get('user_id')}")
        return jsonify({"error": "Solo un usuario root puede modificar a otro usuario root"}), 403
    
    data = request.get_json()
    updates = []
    params  = []

    if "username" in data:
        new_username = data["username"].strip()
        if new_username != current_username:
            updates.append("username = ?")
            params.append(new_username)
    
    if "email" in data:
        new_email = data["email"].strip()
        if new_email != current_email:
            updates.append("email = ?")
            params.append(new_email)
    
    if "role" in data:
        if data["role"] not in [ROLES.ADMIN, ROLES.VENDOR, ROLES.ROOT]:
            logger.warning(f"Intento de asignar rol inválido: {data['role']} por admin ID {session.get('user_id')}")
            data["role"] = current_role  # Mantener el rol actual si es inválido
        new_role = data["role"]
        if new_role == ROLES.ROOT and new_role != current_role and not soy_root:
            logger.warning(f"Intento de ascender a root al usuario ID {target_user_id} por admin ID {session.get('user_id')}")
            return jsonify({"error": "Solo un usuario root puede asignar el rol root"}), 403
        if new_role != current_role:
            updates.append("role = ?")
            params.append(new_role)
    
    if "status" in data:
        try:
            new_status = int(data["status"])
        except (ValueError, TypeError):
            return jsonify({"error": "Estado inválido"}), 400
        if new_status not in (0, 1):
            return jsonify({"error": "Estado inválido"}), 400
            
        if new_status != current_status:
            updates.append("status = ?")
            params.append(new_status)
    
    if "password" in data and data["password"]:
        updates.append("password = ?")
        params.append(generate_password_hash(data["password"]))
    
    if not updates:
        return jsonify({"message": "No hay cambios que aplicar"}), 200

    try:
        params.append(target_user_id)
        db.execute_query(
            f"UPDATE users SET {', '.join(updates)} WHERE id = ?",
            tuple(params),
            fetch=False
        )
        
        db.create_notification(
            user_id=target_user_id,
            title="Tu cuenta ha sido actualizada",
            message="Un administrador ha realizado cambios en tu cuenta. Si no reconoces esta actividad, contacta al soporte.",
            notification_type="info"
        )
        logger.info(f"User ID {target_user_id} updated by admin ID {session.get('user_id')}: {', '.join(updates)}")
        return jsonify({"message": "Usuario actualizado exitosamente"}), 200
    
    except Exception as e:
        # db._cursor() convierte todo sqlite3.Error en DatabaseError, así que un UNIQUE
        # llega acá como DatabaseError("... UNIQUE constraint failed: users.email"),
        # no como sqlite3.IntegrityError.
        msg = str(e).lower()
        if isinstance(e, (sqlite3.IntegrityError, DatabaseError)) and "unique" in msg:
            if "email" in msg:
                return jsonify({"error": "Este correo ya está registrado"}), 409
            if "username" in msg:
                return jsonify({"error": "Este usuario ya existe"}), 409
            return jsonify({"error": "Error de integridad de datos"}), 400
        logger.error(f"Error actualizando usuario {target_user_id}: {str(e)}")
        return jsonify({"error": "Error al actualizar el usuario"}), 500

@users_api.route("/users/<int:target_user_id>", methods=["DELETE"])
@require_permission(PERMS.USERS_MANAGE)
@audit_action("user", "delete", "target_user_id")
def delete_user(target_user_id):
    """Deshabilita un usuario (baja lógica)."""

    if target_user_id == session.get("user_id"):
        return jsonify({"error": "No puedes darte de baja a ti mismo"}), 400
    
    if db.user_exists_by_id(user_id=target_user_id) is False:
        return jsonify({"error": "Usuario no encontrado"}), 404

    target = db.execute_query("SELECT role FROM users WHERE id = ?", (target_user_id,))
    if target and target[0][0] == ROLES.ROOT and session.get("role") != ROLES.ROOT:
        logger.warning(f"Intento de dar de baja al usuario root ID {target_user_id} por admin ID {session.get('user_id')}")
        return jsonify({"error": "Solo un usuario root puede dar de baja a otro usuario root"}), 403

    db.execute_query(
        "UPDATE users SET status = 0 WHERE id = ?",
        (target_user_id,),
        fetch=False
    )
    
    logger.info(f"Usuario ID {target_user_id} dado de baja por admin ID {session.get('user_id')}")
    return jsonify({"message": "Usuario dado de baja"}), 200

@users_api.route("/users/reset-password", methods=["POST"])
@audit_action("user", "reset_password")
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
    
    if "email" not in data:
        return jsonify({"error": "Faltan campos requeridos"}), 400
    
    email = data["email"].strip()
    
    if not _email_valido(email):
        return jsonify({"error": "Formato de correo inválido"}), 400
    
    user = db.get_user_by_email(email)
    
    if not user:
        return jsonify({"error": "Usuario no encontrado"}), 404
    
    logger.info(f"Password reset requested for email: {data.get('email', 'N/A')}")
    
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
@audit_action("user", "change_password")
def change_password():
    """
    Endpoint para cambiar la contraseña después de verificar el código de recuperación.
    
    Requiere login: False.
    
    Request Body (JSON):
        email (str): Correo electrónico del usuario
        code (str): Código de recuperación
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
    
    if not _email_valido(email):
        return jsonify({"error": "Formato de correo inválido"}), 400
    
    if len(new_password) < 6:
        return jsonify({"error": "La nueva contraseña debe tener al menos 6 caracteres"}), 400
    
    user = db.get_user_by_email(email)
    
    if not user:
        return jsonify({"error": "Usuario no encontrado"}), 404
    
    hashed = generate_password_hash(new_password)
    db.update_user_password(email, hashed)
    
    db.delete_reset_code(email=data["email"])
    
    return jsonify({"message": "Contraseña restablecida exitosamente"}), 200

@users_api.route("/login", methods=["POST"])
@audit_action("user", "login")
def api_login():
    """
    Login vía API (JSON) para Thunder Client, Postman, etc.
    
    Body:
        {
            "username": "usuario",
            "password": "contraseña"
        }
    """
    data = request.get_json()
    username = data.get("username", "") if isinstance(data, dict) else ""
    password = data.get("password", "") if isinstance(data, dict) else ""

    if not isinstance(username, str) or not isinstance(password, str):
        return jsonify({"error": "Formato de datos inválido"}), 400

    username = username.strip()
    
    if not username or not password:
        return jsonify({"error": "Usuario y contraseña requeridos"}), 400
    
    rows = db.execute_query(
        "SELECT id, password, role, status FROM users WHERE username = ? OR email = ?", 
        (username, username)
    )
    
    if not rows:
        return jsonify({"error": "Credenciales inválidas"}), 401
    
    user_id, pw_hash, role, status = rows[0]
    
    # Primero la contraseña: así una cuenta desactivada con clave incorrecta responde igual
    # que una cuenta inexistente o con clave incorrecta, y no se puede saber su estado
    # sin conocer la clave.
    if not check_password_hash(pw_hash, password):
        return jsonify({"error": "Credenciales inválidas"}), 401
    
    if status == 0:
        return jsonify({"error": "Error al iniciar sesión"}), 401
    
    if role not in [ROLES.ADMIN, ROLES.VENDOR, ROLES.ROOT]:
        return jsonify({"error": "Rol de usuario no válido"}), 403
    
    # Crear sesión
    session["user_id"] = user_id
    session["username"] = username
    session["role"] = role 
    
    return jsonify({
        "success": True,
        "user_id": user_id,
        "username": username,
        "role": role
    }), 200

@users_api.route("/register", methods=["POST"])
@audit_action("user", "register")
def api_register():
    """
    Registro de nuevo usuario vía API (JSON).
    
    Body:
        {
            "username": "usuario",
            "email": "correo@ejemplo.com",
            "password": "contraseña"
        }
    """
    data = request.get_json()
    username = data.get("username", "").strip()
    email = data.get("email", "").strip()
    password = data.get("password", "")
    
    # Validaciones
    if not username or not email or not password:
        return jsonify({"error": "Faltan campos requeridos"}), 400
    
    if len(password) < 6:
        return jsonify({"error": "Contraseña debe tener mínimo 6 caracteres"}), 400
    
    try:
        UserValidator.validate_email(email)
    except ValidationError as e:
        return jsonify({"error": f"Email inválido: {e.message}"}), 400
    
    try:
        UserValidator.validate(username, password, email, ROLES.VENDOR)
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    
    # Verificar si el usuario ya existe
    if db.user_exists(username, email):
        return jsonify({"error": "Usuario o correo ya existe"}), 409
    
    try:
        pw_hash = generate_password_hash(password)
        db.add_user(
            username=username,
            password=pw_hash,
            email=email,
            role=ROLES.VENDOR,
            status=0,
            application=Var.USER_APPLICATION_PENDING
        )
        logger.info(f"Nuevo usuario registrado: {username} ({email})")
        return jsonify({
            "success": True,
            "message": "Cuenta creada. Espera la aprobación del administrador."
        }), 201
    
    except sqlite3.IntegrityError as e:
        return jsonify({"error": "Error al crear la cuenta"}), 409
    except Exception as e:
        logger.error(f"Error en registro de usuario: {str(e)}")
        return jsonify({"error": "Error interno del servidor"}), 500
    
@users_api.route("/suggest/vendors", methods=["GET"])
@require_auth
def suggest_vendedor():
    """
    Endpoint para autocompletar vendedores activos.
    Requiere login: Sí
    Query Params:
        q (str): Texto de búsqueda para el nombre de usuario del vendedor
    Returns:
        JSON: {"data": [lista de sugerencias de vendedores]}
    Status Codes:
        200: Sugerencias obtenidas exitosamente
        400: Parámetro de búsqueda faltante o vacío
    Example Request:
        GET /suggest/vendors?q=juan
    """
    
    try:
        search = request.args.get("q", "").strip()
        
        if not search:
            return jsonify({"data": []}), 200
        
        rows = db.execute_query(                                              
            """                                                               
            SELECT id, username, email                                        
            FROM users                                                        
            WHERE (role = ? OR role = ?) AND status = 1                      
            AND (username LIKE ? OR email LIKE ?)                            
            LIMIT 10                                                         
            """,                                                              
            (ROLES.VENDOR, ROLES.ADMIN, f"%{search}%", f"%{search}%")
        )  
        
        suggestions = [{"id": r[0], "username": r[1], "email": r[2]} for r in rows]
        
        return jsonify({"data": suggestions}), 200
    
    except Exception as e:
        logger.error(f"Error al obtener sugerencias de vendedores: {str(e)}")
        return jsonify({"error": "Error al obtener sugerencias"}), 500