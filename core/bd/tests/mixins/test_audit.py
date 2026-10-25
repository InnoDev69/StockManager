import pytest

ROOT_ID = 1


def test_log_audit_sin_actor_no_registra_ni_rompe(db):
    db.log_audit(None, "CREATE", "product", entity_id=1)
    res = db.get_audit_log()
    assert res["total"] == 0
    assert res["records"] == []


def test_log_audit_y_filtros(db):
    db.add_user("admin2", "hash", "a2@mail.com", status=1)
    user2_id = db.get_single_row("SELECT id FROM users WHERE username='admin2'")[0]

    db.log_audit(ROOT_ID, "CREATE", "product", entity_id=10, description="Creó yerba")
    db.log_audit(user2_id, "UPDATE", "product", entity_id=10, description="Cambió precio")
    db.log_audit(ROOT_ID, "DELETE", "sale", entity_id=5, description="Anuló venta")

    # Sin filtros
    todo = db.get_audit_log()
    assert todo["total"] == 3

    # Filtro por usuario
    por_user = db.get_audit_log(user_id=user2_id)
    assert por_user["total"] == 1
    assert por_user["records"][0]["username"] == "admin2"

    # Filtro por acción (case-insensitive en el parámetro, se pasa a upper)
    por_accion = db.get_audit_log(action="delete")
    assert por_accion["total"] == 1
    assert por_accion["records"][0]["entity_type"] == "sale"


def test_get_entity_audit_trail_deserializa_json(db):
    db.log_audit(
        ROOT_ID, "UPDATE", "product", entity_id=42,
        old_value={"price": 100}, new_value={"price": 150},
        description="Ajuste por inflación",
    )

    trail = db.get_entity_audit_trail("product", 42)
    assert len(trail) == 1
    entry = trail[0]
    assert entry["username"] == "root"
    assert entry["old_value"] == {"price": 100}
    assert entry["new_value"] == {"price": 150}
    assert entry["description"] == "Ajuste por inflación"