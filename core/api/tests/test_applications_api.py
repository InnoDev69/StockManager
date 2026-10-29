"""
Tests de la API de solicitudes de registro (core/api/applications_api.py):
listado de pendientes, aprobación y rechazo.

Los tests con xfail(strict=True) documentan problemas reales del código actual (el motivo
está en cada marcador). Cuando uno se arregla, pytest avisa con un fallo hasta que se le
saca el marcador.
"""
import pytest
from werkzeug.security import generate_password_hash

from miscellaneous import ROLES, Var

APPS = "/api/applications"
REGISTER = "/api/register"
LOGIN = "/api/login"

PENDING = Var.USER_APPLICATION_PENDING
ACCEPTED = Var.USER_APPLICATION_ACCEPTED
REJECTED = "rejected"      # el literal que usa db.reject_application


# ---------------------------------------------------------------- helpers y fixtures

def crear_usuario(db, username="nuevo", email="nuevo@test.com", password="clave-123456",
                  role=ROLES.VENDOR, status=0, application=PENDING):
    db.add_user(username, generate_password_hash(password), email, role=role, status=status,
                application=application)
    return db.get_single_row("SELECT id FROM users WHERE username = ?", (username,))[0]


def estado(db, user_id):
    """(status, application) del usuario."""
    return db.get_single_row("SELECT status, application FROM users WHERE id = ?", (user_id,))


def login(client, usuario, password="clave-123456"):
    return client.post(LOGIN, json={"username": usuario, "password": password})


@pytest.fixture
def sin_permisos(monkeypatch):
    """Ningún rol (salvo root, que siempre pasa) tiene permisos."""
    monkeypatch.setattr("core.services.permissions_service.has_permission", lambda *a, **k: False)


# ================================================================ GET /applications

def test_listar_solo_las_solicitudes_pendientes(client, db):
    pendiente = crear_usuario(db, "pendiente", "pendiente@test.com")
    crear_usuario(db, "aceptado", "aceptado@test.com", status=1, application=ACCEPTED)
    crear_usuario(db, "rechazado", "rechazado@test.com", application=REJECTED)

    r = client.get(APPS)

    assert r.status_code == 200
    body = r.get_json()
    assert [u["id"] for u in body["data"]] == [pendiente]
    assert body["total"] == 1


def test_listar_devuelve_los_campos_esperados_y_nunca_la_contrasena(client, db):
    uid = crear_usuario(db)

    fila = client.get(APPS).get_json()["data"][0]

    assert set(fila) == {"id", "username", "email", "created_at"}
    assert (fila["id"], fila["username"], fila["email"]) == (uid, "nuevo", "nuevo@test.com")


def test_listar_sin_solicitudes_devuelve_una_lista_vacia(client):
    body = client.get(APPS).get_json()

    assert body["data"] == []
    assert body["total"] == 0


def test_listar_pagina_las_solicitudes(client, db):
    for i in range(3):
        crear_usuario(db, f"pend{i}", f"pend{i}@test.com")

    p1 = client.get(APPS, query_string={"limit": 2, "page": 1}).get_json()
    p2 = client.get(APPS, query_string={"limit": 2, "page": 2}).get_json()
    p3 = client.get(APPS, query_string={"limit": 2, "page": 3}).get_json()

    assert (p1["total"], p1["pages"], len(p1["data"])) == (3, 2, 2)
    assert len(p2["data"]) == 1
    assert p3["data"] == []
    assert {u["id"] for u in p1["data"]}.isdisjoint({u["id"] for u in p2["data"]})


def test_listar_por_defecto_trae_10_por_pagina(client, db):
    for i in range(12):
        crear_usuario(db, f"pend{i:02d}", f"pend{i:02d}@test.com")

    body = client.get(APPS).get_json()

    assert len(body["data"]) == 10
    assert body["total"] == 12


def test_listar_con_pagina_cero_trae_la_primera(client, db):
    crear_usuario(db)

    r = client.get(APPS, query_string={"page": 0})

    assert r.status_code == 200
    assert len(r.get_json()["data"]) == 1


@pytest.mark.xfail(strict=True, reason="page y limit no se validan: un valor no numérico da 500 (con el mensaje interno), "
                                       "limit=0 da 500 por división por cero y limit=-1 devuelve TODAS las filas "
                                       "(en SQLite un LIMIT negativo significa 'sin límite')")
@pytest.mark.parametrize("query", [{"page": "abc"}, {"limit": "abc"}, {"limit": 0}, {"limit": -1}])
def test_listar_con_parametros_de_paginacion_invalidos_no_deberia_fallar_ni_traer_todo(client, db, query):
    for i in range(15):
        crear_usuario(db, f"pend{i:02d}", f"pend{i:02d}@test.com")

    r = client.get(APPS, query_string=query)

    assert r.status_code == 200
    assert len(r.get_json()["data"]) <= 10


def test_listar_sin_permiso_devuelve_403(vendor_client, sin_permisos):
    assert vendor_client.get(APPS).status_code == 403


def test_listar_sin_sesion_devuelve_401(anon_client):
    assert anon_client.get(APPS).status_code == 401


# ================================================================ POST /applications/<id>/approve

def test_aprobar_activa_la_cuenta(client, db):
    uid = crear_usuario(db)

    r = client.post(f"{APPS}/{uid}/approve")

    assert r.status_code == 200
    assert r.get_json()["message"] == "Solicitud aprobada"
    assert estado(db, uid) == (1, ACCEPTED)


def test_aprobar_saca_la_solicitud_del_listado(client, db):
    uid = crear_usuario(db)
    client.post(f"{APPS}/{uid}/approve")

    assert client.get(APPS).get_json()["data"] == []


def test_aprobar_solo_afecta_a_ese_usuario(client, db):
    uid = crear_usuario(db, "uno", "uno@test.com")
    otro = crear_usuario(db, "otro", "otro@test.com")

    client.post(f"{APPS}/{uid}/approve")

    assert estado(db, otro) == (0, PENDING)


def test_flujo_completo_registro_aprobacion_y_login(client, anon_client, db):
    anon_client.post(REGISTER, json={"username": "nuevo", "email": "nuevo@test.com",
                                     "password": "clave-123456"})
    uid = db.get_single_row("SELECT id FROM users WHERE username = 'nuevo'")[0]
    assert login(anon_client, "nuevo").status_code == 401          # todavía no puede entrar

    client.post(f"{APPS}/{uid}/approve")

    r = login(anon_client, "nuevo")
    assert r.status_code == 200
    assert r.get_json()["role"] == ROLES.VENDOR


def test_aprobar_sin_permiso_devuelve_403(vendor_client, db, sin_permisos):
    uid = crear_usuario(db)

    r = vendor_client.post(f"{APPS}/{uid}/approve")

    assert r.status_code == 403
    assert estado(db, uid) == (0, PENDING)


def test_aprobar_sin_sesion_devuelve_401(anon_client, db):
    uid = crear_usuario(db)

    r = anon_client.post(f"{APPS}/{uid}/approve")

    assert r.status_code == 401
    assert estado(db, uid) == (0, PENDING)


@pytest.mark.xfail(strict=True, reason="No verifica que el usuario exista: responde 200 'Solicitud aprobada'; debería dar 404")
def test_aprobar_un_usuario_inexistente_deberia_dar_404(client):
    assert client.post(f"{APPS}/99999/approve").status_code == 404


@pytest.mark.xfail(strict=True, reason="No verifica que la solicitud esté pendiente: 'aprobar' a un usuario dado de baja "
                                       "(status 0, solicitud ya aceptada) lo reactiva, salteándose la baja de users_api")
def test_aprobar_no_deberia_reactivar_a_un_usuario_dado_de_baja(client, db):
    uid = crear_usuario(db, "baja", "baja@test.com", status=0, application=ACCEPTED)

    r = client.post(f"{APPS}/{uid}/approve")

    assert r.status_code in (400, 404, 409)
    assert estado(db, uid) == (0, ACCEPTED)


@pytest.mark.xfail(strict=True, reason="No verifica que la solicitud esté pendiente: una solicitud ya rechazada "
                                       "se puede aprobar después sin ningún aviso")
def test_aprobar_una_solicitud_ya_rechazada_deberia_rechazarse(client, db):
    uid = crear_usuario(db, application=REJECTED)

    r = client.post(f"{APPS}/{uid}/approve")

    assert r.status_code in (400, 404, 409)
    assert estado(db, uid) == (0, REJECTED)


# ================================================================ POST /applications/<id>/reject

def test_rechazar_marca_la_solicitud_y_deja_la_cuenta_inactiva(client, db):
    uid = crear_usuario(db)

    r = client.post(f"{APPS}/{uid}/reject")

    assert r.status_code == 200
    assert r.get_json()["message"] == "Solicitud rechazada"
    assert estado(db, uid) == (0, REJECTED)


def test_rechazar_saca_la_solicitud_del_listado(client, db):
    uid = crear_usuario(db)
    client.post(f"{APPS}/{uid}/reject")

    assert client.get(APPS).get_json()["data"] == []


def test_un_usuario_rechazado_no_puede_loguearse(client, anon_client, db):
    crear_usuario(db)
    uid = db.get_single_row("SELECT id FROM users WHERE username = 'nuevo'")[0]
    client.post(f"{APPS}/{uid}/reject")

    assert login(anon_client, "nuevo").status_code == 401


def test_rechazar_solo_afecta_a_ese_usuario(client, db):
    uid = crear_usuario(db, "uno", "uno@test.com")
    otro = crear_usuario(db, "otro", "otro@test.com")

    client.post(f"{APPS}/{uid}/reject")

    assert estado(db, otro) == (0, PENDING)


def test_rechazar_sin_permiso_devuelve_403(vendor_client, db, sin_permisos):
    uid = crear_usuario(db)

    r = vendor_client.post(f"{APPS}/{uid}/reject")

    assert r.status_code == 403
    assert estado(db, uid) == (0, PENDING)


def test_rechazar_sin_sesion_devuelve_401(anon_client, db):
    uid = crear_usuario(db)

    r = anon_client.post(f"{APPS}/{uid}/reject")

    assert r.status_code == 401
    assert estado(db, uid) == (0, PENDING)


@pytest.mark.xfail(strict=True, reason="No verifica que el usuario exista: responde 200 'Solicitud rechazada'; debería dar 404")
def test_rechazar_un_usuario_inexistente_deberia_dar_404(client):
    assert client.post(f"{APPS}/99999/reject").status_code == 404


@pytest.mark.xfail(strict=True, reason="No verifica que la solicitud esté pendiente: 'rechazar' a un usuario activo lo marca "
                                       "como rechazado aunque siga con status 1 (queda inconsistente)")
def test_rechazar_a_un_usuario_activo_deberia_rechazarse(client, db):
    uid = crear_usuario(db, "activo", "activo@test.com", status=1, application=ACCEPTED)

    r = client.post(f"{APPS}/{uid}/reject")

    assert r.status_code in (400, 404, 409)
    assert estado(db, uid) == (1, ACCEPTED)
