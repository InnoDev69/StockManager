from functools import wraps
from flask import session, request
from bd.bdInstance import db
from tools.logger import logger
import json

# ──────────────────────────────────────────────
#  Tablas de traducción para descripciones
# ──────────────────────────────────────────────

ENTITY_LABELS = {
    "user":        "Usuario",
    "product":     "Producto",
    "sale":        "Venta",
    "application": "Aplicación",
}

FIELD_LABELS = {
    # users
    "username":     "Nombre de usuario",
    "email":        "Email",
    "role":         "Rol",
    "status":       "Estado",
    # items / products
    "name":         "Nombre",
    "price":        "Precio",
    "quantity":     "Cantidad",
    "min_quantity": "Stock mínimo",
    # sales
    "item_id":      "Producto (ID)",
    "total_price":  "Total",
}

_CURRENCY_FIELDS = {"price", "total_price"}

_SKIP_ON_CREATE = {"password", "id"}

ACTION_LABELS = {
    "create": "Creación",
    "update": "Actualización",
    "delete": "Eliminación",
    "get":    "Consulta",
    "post":   "Acción",
}


def get_client_ip():
    """Obtiene la IP real del cliente (considerando proxies)."""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr or 'Unknown'


def _label(field: str) -> str:
    """Devuelve el label legible de un campo, o el nombre original si no está mapeado."""
    return FIELD_LABELS.get(field, field.replace("_", " ").capitalize())


def _entity_label(entity_type: str) -> str:
    return ENTITY_LABELS.get(entity_type, entity_type.capitalize())


def _format_value(field: str, value) -> str:
    """Formatea un valor según el tipo de campo."""
    if value is None:
        return "—"
    if field in _CURRENCY_FIELDS:
        try:
            return f"${float(value):,.2f}"
        except (TypeError, ValueError):
            pass
    return f"'{value}'"


def _build_create_description(entity_type: str, data: dict) -> str:
    """
    Genera una descripción de creación mostrando campo: valor para cada campo relevante.
    Ejemplo: "Nuevo Usuario creado — Nombre de usuario: 'jdoe', Email: 'j@doe.com', Rol: 'admin'"
    """
    entity_label = _entity_label(entity_type)
    parts = [
        f"{_label(k)}: {_format_value(k, v)}"
        for k, v in data.items()
        if k not in _SKIP_ON_CREATE
    ]
    detail = ", ".join(parts) if parts else "sin detalle"
    return f"Nuevo {entity_label} creado — {detail}"


def _build_delete_description(entity_type: str, entity_id, old_value: dict | None) -> str:
    """
    Genera una descripción de eliminación con el identificador principal de la entidad.
    Ejemplo: "Usuario eliminado — Nombre de usuario: 'jdoe' (ID: 5)"
    """
    entity_label = _entity_label(entity_type)
    id_str = f" (ID: {entity_id})" if entity_id is not None else ""

    if old_value:
        name_field = next(
            (f for f in ("username", "name", "email") if f in old_value),
            None
        )
        if name_field:
            name_display = _format_value(name_field, old_value[name_field])
            return f"{entity_label} eliminado — {_label(name_field)}: {name_display}{id_str}"

    return f"{entity_label} eliminado{id_str}"


def _build_default_description(action: str, entity_type: str, entity_id=None) -> str:
    """Descripción genérica de fallback con contexto real."""
    action_label = ACTION_LABELS.get(action, action.capitalize())
    entity_label = _entity_label(entity_type)
    id_str = f" #{entity_id}" if entity_id is not None else ""
    return f"{action_label} de {entity_label}{id_str}"


def _compare_changes(old_value: dict | None, new_value: dict | None) -> str:
    """
    Compara dos snapshots y devuelve una descripción legible de los cambios.
    Ejemplo: "Cambios: Rol: 'viewer' → 'admin'; Estado: 'active' → 'inactive'"
    """
    if not old_value or not new_value:
        return "Cambios registrados (snapshot parcial)"

    changes = []
    for key in new_value:
        label = _label(key)
        old_v = old_value.get(key)
        new_v = new_value[key]

        if key not in old_value:
            changes.append(f"{label}: {_format_value(key, new_v)} (campo nuevo)")
        elif old_v != new_v:
            changes.append(
                f"{label}: {_format_value(key, old_v)} → {_format_value(key, new_v)}"
            )

    if not changes:
        return "Sin cambios detectados"

    return "Cambios: " + "; ".join(changes)


def audit_action(entity_type, action_name=None, id_param=None):
    """
    Decorator para registrar automáticamente acciones en auditoría.

    Args:
        entity_type: "user" | "product" | "sale" | "application"
        action_name: "create" | "update" | "delete" (default: método HTTP)
        id_param: nombre del parámetro con el ID (ej: 'user_id', 'product_id')

    Ejemplo:
        @audit_action("user", "update", "target_user_id")
        def update_user(target_user_id):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            actor_id = session.get('user_id')
            ip_address = get_client_ip()
            action = action_name or request.method.lower()

            entity_id = kwargs.get(id_param) if id_param else None

            old_value = None
            new_value = None
            changes_description = ""

            if action in ("update", "delete") and entity_id and id_param:
                old_value = _get_entity_before(entity_type, entity_id)

            try:
                response = func(*args, **kwargs)
                status_code = response[1] if isinstance(response, tuple) else 200

                if action == "update" and entity_id and id_param:
                    new_value = _get_entity_before(entity_type, entity_id)
                    changes_description = _compare_changes(old_value, new_value)

                if action == "create":
                    data = request.get_json() or {}
                    new_value = {k: v for k, v in data.items() if k not in ['password']}
                    changes_description = _build_create_description(entity_type, new_value)

                if action == "delete":
                    changes_description = _build_delete_description(entity_type, entity_id, old_value)

                status = 'success' if status_code < 400 else 'error'

                db.log_audit(
                    actor_id=actor_id,
                    action=action,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    old_value=old_value,
                    new_value=new_value,
                    description=changes_description or _build_default_description(action, entity_type, entity_id),
                    ip_address=ip_address,
                    status=status
                )

                return response

            except Exception as e:
                entity_label = _entity_label(entity_type)
                db.log_audit(
                    actor_id=actor_id,
                    action=action,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    description=f"Error al ejecutar {ACTION_LABELS.get(action, action).lower()} de {entity_label}: {str(e)[:120]}",
                    ip_address=ip_address,
                    status='error'
                )
                logger.error(f"[Audit] Error en {func.__name__}: {str(e)}")
                raise

        return wrapper
    return decorator


def _get_entity_before(entity_type, entity_id):
    """Obtiene los datos actuales de una entidad ANTES de ser modificada."""
    try:
        if entity_type == "user":
            rows = db.execute_query(
                "SELECT id, username, email, role, status FROM users WHERE id = ?",
                (entity_id,)
            )
            if rows:
                r = rows[0]
                return {
                    "id": r[0],
                    "username": r[1],
                    "email": r[2],
                    "role": r[3],
                    "status": r[4]
                }

        elif entity_type == "product":
            rows = db.execute_query(
                "SELECT id, name, price, quantity, min_quantity FROM items WHERE id = ?",
                (entity_id,)
            )
            if rows:
                r = rows[0]
                return {
                    "id": r[0],
                    "name": r[1],
                    "price": r[2],
                    "quantity": r[3],
                    "min_quantity": r[4]
                }

        elif entity_type == "sale":
            rows = db.execute_query(
                "SELECT id, item_id, quantity, total_price, status FROM sales WHERE id = ?",
                (entity_id,)
            )
            if rows:
                r = rows[0]
                return {
                    "id": r[0],
                    "item_id": r[1],
                    "quantity": r[2],
                    "total_price": r[3],
                    "status": r[4]
                }

    except Exception as e:
        logger.error(f"Error getting entity {entity_type}:{entity_id} - {e}")

    return None