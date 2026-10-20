import pytest


@pytest.fixture
def solicitantes(db):
    """Crea 3 usuarios con application='pending' (default de add_user)."""
    ids = []
    for i in range(1, 4):
        db.add_user(f"postulante{i}", "hash", f"p{i}@mail.com")
        uid = db.get_single_row("SELECT id FROM users WHERE username=?", (f"postulante{i}",))[0]
        ids.append(uid)
    return ids


def test_get_pending_applications_y_paginacion(db, solicitantes):
    # root tiene application='accepted', solo deben salir los 3 solicitantes
    res = db.get_pending_applications(page=1, limit=2)
    assert res["total"] == 3
    assert res["pages"] == 2
    assert res["page"] == 1
    assert len(res["data"]) == 2

    res_p2 = db.get_pending_applications(page=2, limit=2)
    assert len(res_p2["data"]) == 1


def test_approve_application_activa_al_usuario(db, solicitantes):
    uid = solicitantes[0]
    assert db.approve_application(uid) is True

    row = db.get_single_row("SELECT application, status FROM users WHERE id=?", (uid,))
    assert row == ("accepted", 1)
    assert db.get_pending_applications()["total"] == 2


def test_reject_application_mantiene_inactivo(db, solicitantes):
    uid = solicitantes[0]
    assert db.reject_application(uid) is True

    row = db.get_single_row("SELECT application, status FROM users WHERE id=?", (uid,))
    assert row == ("rejected", 0)
    assert db.get_pending_applications()["total"] == 2