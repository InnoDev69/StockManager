"""
Tests de la API de usuarios (core/api/users_api.py):
ABM de usuarios, login, registro y recuperación de contraseña.

Si algún test queda con xfail(strict=True), documenta un problema real del código actual
(el motivo está en el marcador). Cuando se arregla, pytest avisa con un fallo hasta que
se le saca el marcador.
"""
import sys

import pytest
from werkzeug.security import check_password_hash, generate_password_hash

from miscellaneous import ROLES, Var

USERS = "/api/users"
LOGIN = "/api/login"
REGISTER = "/api/register"
SUGGEST = "/api/suggest/vendors"
RESET = "/api/users/reset-password"
VALIDATE = "/api/users/validate-code"
CHANGE = "/api/users/reset-password/change-password"


# ---------------------------------------------------------------- helpers y fixtures

def crear_usuario(db, username="juan", email="juan@test.com", password="clave-123456",
                  role=ROLES.VENDOR, status=1):
    db.add_user(username, generate_password_hash(password), email, role=role, status=status,
                application=Var.USER_APPLICATION_ACCEPTED)
    return db.get_single_row("SELECT id FROM users WHERE username = ?", (username,))[0]


def fila(db, username):
    """(email, role, status, application) de un usuario, o None."""
    return db.get_single_row(
        "SELECT email, role, status, application FROM users WHERE username = ?", (username,))


def hash_de(db, user_id):
    return db.get_single_row("SELECT password FROM users WHERE id = ?", (user_id,))[0]


def iniciar_sesion(client, user_id, role):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["role"] = role
    return client


def login(client, usuario, password):
    return client.post(LOGIN, json={"username": usuario, "password": password})


@pytest.fixture
def sin_permisos(monkeypatch):
    """Ningún rol (salvo root, que siempre pasa) tiene permisos."""
    monkeypatch.setattr("core.services.permissions_service.has_permission", lambda *a, **k: False)


@pytest.fixture
def con_todos_los_permisos(monkeypatch):
    """Simula un admin al que se le dio USERS_MANAGE (y todo lo demás)."""
    """ Issue URL: https://github.com/InnoDev69/StockManager/issues/57 """
    monkeypatch.setattr("core.services.permissions_service.has_permission", lambda *a, **k: True)


@pytest.fixture
def admin_client(app, db):
    admin_id = crear_usuario(db, "admin1", "admin1@test.com", role=ROLES.ADMIN)
    return iniciar_sesion(app.test_client(), admin_id, ROLES.ADMIN)


@pytest.fixture
def emails(monkeypatch):
    """Captura los mails que enviaría la app (nunca se manda uno real)."""
    enviados = []
    users_mod = sys.modules["core.api.users_api"]

    def falso(to, subject=None, body=None, *args, **kwargs):
        enviados.append({"to": to, "subject": subject, "body": body})

    monkeypatch.setattr(users_mod.email_sender, "send_email", falso)
    return enviados


def nuevo_usuario(**extra):
    cuerpo = {"username": "maria", "email": "maria@test.com", "password": "clave-123456",
              "role": ROLES.VENDOR}
    cuerpo.update(extra)
    return cuerpo


# ================================================================ GET /users

def test_listar_usuarios_incluye_campos_y_nunca_la_contrasena(client, db):
    crear_usuario(db)

    r = client.get(USERS)

    assert r.status_code == 200
    body = r.get_json()
    assert body["total"] == 2          # root + juan
    assert {u["username"] for u in body["data"]} == {"root", "juan"}
    for u in body["data"]:
        assert set(u) == {"id", "username", "email", "role", "status", "created_at"}


def test_listar_usuarios_busca_por_nombre_o_email(client, db):
    crear_usuario(db, "juan", "juan@test.com")
    crear_usuario(db, "pedro", "pedro@otro.com")

    por_nombre = client.get(USERS, query_string={"search": "jua"}).get_json()
    por_email = client.get(USERS, query_string={"search": "otro.com"}).get_json()

    assert [u["username"] for u in por_nombre["data"]] == ["juan"]
    assert [u["username"] for u in por_email["data"]] == ["pedro"]
    assert por_nombre["total"] == 1


def test_listar_usuarios_pagina(client, db):
    for i in range(4):
        crear_usuario(db, f"user{i}", f"user{i}@test.com")     # + root = 5

    p1 = client.get(USERS, query_string={"limit": 2, "page": 1}).get_json()
    p3 = client.get(USERS, query_string={"limit": 2, "page": 3}).get_json()
    p9 = client.get(USERS, query_string={"limit": 2, "page": 9}).get_json()

    assert (p1["total"], p1["pages"], len(p1["data"])) == (5, 3, 2)
    assert len(p3["data"]) == 1
    assert p9["data"] == []


@pytest.mark.parametrize("query, esperado", [
    ({"limit": 1000}, {"limit": 100, "page": 1}),
    ({"limit": 0}, {"limit": 1, "page": 1}),
    ({"page": 0}, {"limit": 10, "page": 1}),
    ({"page": "abc", "limit": "xyz"}, {"limit": 10, "page": 1}),
])
def test_listar_usuarios_corrige_parametros_de_paginacion(client, query, esperado):
    body = client.get(USERS, query_string=query).get_json()

    assert {"limit": body["limit"], "page": body["page"]} == esperado


def test_listar_usuarios_sin_permiso_devuelve_403(vendor_client, sin_permisos):
    assert vendor_client.get(USERS).status_code == 403


def test_listar_usuarios_sin_sesion_devuelve_401(anon_client):
    assert anon_client.get(USERS).status_code == 401


# ================================================================ GET /users/<id>

def test_obtener_un_usuario(client, db):
    uid = crear_usuario(db)

    r = client.get(f"{USERS}/{uid}")

    assert r.status_code == 200
    body = r.get_json()
    assert (body["id"], body["username"], body["email"], body["role"], body["status"]) == \
        (uid, "juan", "juan@test.com", ROLES.VENDOR, 1)
    assert "password" not in body


def test_obtener_un_usuario_inexistente(client):
    r = client.get(f"{USERS}/99999")

    assert r.status_code == 404
    assert r.get_json()["error"] == "Usuario no encontrado"


def test_obtener_un_usuario_sin_permiso_devuelve_403(vendor_client, sin_permisos):
    assert vendor_client.get(f"{USERS}/1").status_code == 403


def test_obtener_un_usuario_sin_sesion_devuelve_401(anon_client):
    assert anon_client.get(f"{USERS}/1").status_code == 401


# ================================================================ POST /users

def test_crear_usuario(client, db):
    r = client.post(USERS, json=nuevo_usuario(role=ROLES.ADMIN))

    assert r.status_code == 201
    assert r.get_json()["message"] == "Usuario creado exitosamente"
    email, role, status, application = fila(db, "maria")
    assert (email, role, status) == ("maria@test.com", ROLES.ADMIN, 1)
    assert application == Var.USER_APPLICATION_ACCEPTED


def test_crear_usuario_guarda_la_contrasena_hasheada_y_permite_loguearse(client, db, anon_client):
    client.post(USERS, json=nuevo_usuario())

    guardado = db.get_single_row("SELECT password FROM users WHERE username = 'maria'")[0]
    assert guardado != "clave-123456"
    assert check_password_hash(guardado, "clave-123456")
    assert login(anon_client, "maria", "clave-123456").status_code == 200


def test_crear_usuario_recorta_espacios_del_nombre(client, db):
    client.post(USERS, json=nuevo_usuario(username="  maria  "))

    assert fila(db, "maria") is not None


@pytest.mark.parametrize("faltante", ["username", "email", "password", "role"])
def test_crear_usuario_sin_campos_requeridos(client, db, faltante):
    cuerpo = nuevo_usuario()
    del cuerpo[faltante]

    r = client.post(USERS, json=cuerpo)

    assert r.status_code == 400
    assert r.get_json()["error"] == "Faltan campos requeridos"
    assert fila(db, "maria") is None


def test_crear_usuario_con_email_repetido(client, db):
    crear_usuario(db, "juan", "maria@test.com")

    r = client.post(USERS, json=nuevo_usuario())

    assert r.status_code == 409
    assert r.get_json()["error"] == "El correo ya está registrado"
    assert fila(db, "maria") is None


def test_crear_usuario_con_email_invalido(client, db):
    r = client.post(USERS, json=nuevo_usuario(email="no-es-un-mail"))

    assert r.status_code == 400
    assert fila(db, "maria") is None


def test_crear_usuario_con_rol_invalido(client, db):
    r = client.post(USERS, json=nuevo_usuario(role="superheroe"))

    assert r.status_code == 400
    assert fila(db, "maria") is None


def test_crear_usuario_con_nombre_repetido(client, db):
    crear_usuario(db, "maria", "otra@test.com")

    r = client.post(USERS, json=nuevo_usuario())      # mismo username, otro email

    assert r.status_code == 409
    assert r.get_json()["error"] == "Este usuario ya existe"


def test_crear_usuario_sin_permiso_devuelve_403(vendor_client, db, sin_permisos):
    r = vendor_client.post(USERS, json=nuevo_usuario())

    assert r.status_code == 403
    assert fila(db, "maria") is None


def test_crear_usuario_sin_sesion_devuelve_401(anon_client):
    assert anon_client.post(USERS, json=nuevo_usuario()).status_code == 401


# ================================================================ PUT /users/<id>

def test_actualizar_nombre_email_rol_y_estado(client, db):
    uid = crear_usuario(db)

    r = client.put(f"{USERS}/{uid}", json={"username": "juan2", "email": "juan2@test.com",
                                           "role": ROLES.ADMIN, "status": 0})

    assert r.status_code == 200
    assert r.get_json()["message"] == "Usuario actualizado exitosamente"
    assert fila(db, "juan2")[:3] == ("juan2@test.com", ROLES.ADMIN, 0)


def test_actualizar_avisa_al_usuario_con_una_notificacion(client, db):
    uid = crear_usuario(db)

    client.put(f"{USERS}/{uid}", json={"email": "nuevo@test.com"})

    n = db.get_single_row("SELECT COUNT(*) FROM notifications WHERE user_id = ?", (uid,))[0]
    assert n == 1


def test_actualizar_sin_cambios_reales_no_modifica_ni_notifica(client, db):
    uid = crear_usuario(db)

    r = client.put(f"{USERS}/{uid}", json={"username": "juan", "email": "juan@test.com",
                                           "role": ROLES.VENDOR, "status": 1})

    assert r.status_code == 200
    assert r.get_json()["message"] == "No hay cambios que aplicar"
    n = db.get_single_row("SELECT COUNT(*) FROM notifications WHERE user_id = ?", (uid,))[0]
    assert n == 0


def test_actualizar_cambia_la_contrasena_y_la_guarda_hasheada(client, db, anon_client):
    uid = crear_usuario(db)

    client.put(f"{USERS}/{uid}", json={"password": "otra-clave-9"})

    assert hash_de(db, uid) != "otra-clave-9"
    assert login(anon_client, "juan", "otra-clave-9").status_code == 200
    assert login(anon_client, "juan", "clave-123456").status_code == 401


def test_actualizar_con_contrasena_vacia_no_la_cambia(client, db):
    uid = crear_usuario(db)
    antes = hash_de(db, uid)

    client.put(f"{USERS}/{uid}", json={"password": ""})

    assert hash_de(db, uid) == antes


def test_actualizar_con_rol_invalido_lo_ignora(client, db):
    uid = crear_usuario(db)

    r = client.put(f"{USERS}/{uid}", json={"role": "superheroe"})

    assert r.status_code == 200
    assert fila(db, "juan")[1] == ROLES.VENDOR


def test_actualizar_un_usuario_inexistente(client):
    r = client.put(f"{USERS}/99999", json={"email": "x@test.com"})

    assert r.status_code == 404
    assert r.get_json()["error"] == "Usuario no encontrado"


def test_actualizar_con_email_de_otro_usuario(client, db):
    crear_usuario(db, "ana", "ana@test.com")
    uid = crear_usuario(db, "juan", "juan@test.com")

    r = client.put(f"{USERS}/{uid}", json={"email": "ana@test.com"})

    assert r.status_code == 409
    assert fila(db, "juan")[0] == "juan@test.com"


@pytest.mark.parametrize("estado", ["abc", None, [1], 2, -1, "5"])
def test_actualizar_con_estado_invalido_da_400(client, db, estado):
    uid = crear_usuario(db)

    r = client.put(f"{USERS}/{uid}", json={"status": estado})

    assert r.status_code == 400
    assert r.get_json()["error"] == "Estado inválido"
    assert fila(db, "juan")[2] == 1


def test_actualizar_sin_permiso_devuelve_403(vendor_client, db, sin_permisos):
    uid = crear_usuario(db)

    r = vendor_client.put(f"{USERS}/{uid}", json={"role": ROLES.ADMIN})

    assert r.status_code == 403
    assert fila(db, "juan")[1] == ROLES.VENDOR


def test_actualizar_sin_sesion_devuelve_401(anon_client):
    assert anon_client.put(f"{USERS}/1", json={"email": "x@test.com"}).status_code == 401


# ================================================================ DELETE /users/<id>

def test_dar_de_baja_es_logico(client, db):
    uid = crear_usuario(db)

    r = client.delete(f"{USERS}/{uid}")

    assert r.status_code == 200
    assert r.get_json()["message"] == "Usuario dado de baja"
    assert fila(db, "juan")[2] == 0          # sigue existiendo, con status 0


def test_un_usuario_dado_de_baja_no_puede_loguearse(client, db, anon_client):
    uid = crear_usuario(db)
    client.delete(f"{USERS}/{uid}")

    assert login(anon_client, "juan", "clave-123456").status_code == 401


def test_no_se_puede_dar_de_baja_a_uno_mismo(client, db):
    r = client.delete(f"{USERS}/1")        # el cliente es root, id 1

    assert r.status_code == 400
    assert r.get_json()["error"] == "No puedes darte de baja a ti mismo"
    assert db.get_single_row("SELECT status FROM users WHERE id = 1")[0] == 1


def test_dar_de_baja_un_usuario_inexistente(client):
    r = client.delete(f"{USERS}/99999")

    assert r.status_code == 404
    assert r.get_json()["error"] == "Usuario no encontrado"


def test_dar_de_baja_sin_permiso_devuelve_403(vendor_client, db, sin_permisos):
    uid = crear_usuario(db)

    assert vendor_client.delete(f"{USERS}/{uid}").status_code == 403
    assert fila(db, "juan")[2] == 1


def test_dar_de_baja_sin_sesion_devuelve_401(anon_client):
    assert anon_client.delete(f"{USERS}/2").status_code == 401


# ================================================================ protección del root
# Simulan un admin con USERS_MANAGE: aun con ese permiso, no puede tocar a un root.

def test_un_admin_no_puede_ascender_a_root(admin_client, db, con_todos_los_permisos):
    uid = crear_usuario(db)

    r = admin_client.put(f"{USERS}/{uid}", json={"role": ROLES.ROOT})

    assert r.status_code == 403
    assert fila(db, "juan")[1] == ROLES.VENDOR


def test_un_admin_no_puede_crear_un_root(admin_client, db, con_todos_los_permisos):
    r = admin_client.post(USERS, json=nuevo_usuario(role=ROLES.ROOT))

    assert r.status_code in (400, 403)
    assert fila(db, "maria") is None


def test_un_admin_no_puede_cambiar_la_clave_del_root(admin_client, db, con_todos_los_permisos):
    antes = hash_de(db, 1)

    r = admin_client.put(f"{USERS}/1", json={"password": "hackeada-123"})

    assert r.status_code == 403
    assert hash_de(db, 1) == antes


def test_un_admin_no_puede_dar_de_baja_al_root(admin_client, db, con_todos_los_permisos):
    r = admin_client.delete(f"{USERS}/1")

    assert r.status_code == 403
    assert db.get_single_row("SELECT status FROM users WHERE id = 1")[0] == 1


def test_un_root_si_puede_crear_otro_root(client, db):
    r = client.post(USERS, json=nuevo_usuario(role=ROLES.ROOT))

    assert r.status_code == 201
    assert fila(db, "maria")[1] == ROLES.ROOT


# ================================================================ POST /login

def test_login_con_usuario(anon_client, db):
    uid = crear_usuario(db)

    r = login(anon_client, "juan", "clave-123456")

    assert r.status_code == 200
    assert r.get_json() == {"success": True, "user_id": uid, "username": "juan", "role": ROLES.VENDOR}
    with anon_client.session_transaction() as sess:
        assert (sess["user_id"], sess["role"]) == (uid, ROLES.VENDOR)


def test_login_con_email(anon_client, db):
    uid = crear_usuario(db)

    r = login(anon_client, "juan@test.com", "clave-123456")

    assert r.status_code == 200
    assert r.get_json()["user_id"] == uid


def test_login_recorta_espacios_del_usuario(anon_client, db):
    crear_usuario(db)

    assert login(anon_client, "  juan  ", "clave-123456").status_code == 200


def test_login_con_contrasena_incorrecta_no_abre_sesion(anon_client, db):
    crear_usuario(db)

    r = login(anon_client, "juan", "mala")

    assert r.status_code == 401
    assert r.get_json()["error"] == "Credenciales inválidas"
    with anon_client.session_transaction() as sess:
        assert "user_id" not in sess


def test_login_no_revela_si_el_usuario_existe(anon_client, db):
    crear_usuario(db)

    mala_clave = login(anon_client, "juan", "mala")
    no_existe = login(anon_client, "fantasma", "mala")

    assert mala_clave.status_code == no_existe.status_code == 401
    assert mala_clave.get_json() == no_existe.get_json()


@pytest.mark.parametrize("cuerpo", [
    {}, {"username": "juan"}, {"password": "x"}, {"username": "", "password": "x"},
    {"username": "   ", "password": "x"}, {"username": "juan", "password": ""},
])
def test_login_con_campos_vacios_o_faltantes(anon_client, cuerpo):
    r = anon_client.post(LOGIN, json=cuerpo)

    assert r.status_code == 400
    assert r.get_json()["error"] == "Usuario y contraseña requeridos"


def test_login_de_usuario_desactivado_con_la_clave_correcta_no_abre_sesion(anon_client, db):
    crear_usuario(db, status=0)

    r = login(anon_client, "juan", "clave-123456")

    assert r.status_code == 401
    with anon_client.session_transaction() as sess:
        assert "user_id" not in sess


def test_login_desactivado_con_clave_incorrecta_se_ve_igual_que_un_usuario_inexistente(anon_client, db):
    """Si la respuesta cambiara, cualquiera sabría que la cuenta existe y está desactivada."""
    crear_usuario(db, status=0)

    desactivado = login(anon_client, "juan", "mala")
    no_existe = login(anon_client, "fantasma", "mala")

    assert desactivado.status_code == no_existe.status_code == 401
    assert desactivado.get_json() == no_existe.get_json()


def test_login_con_rol_invalido_en_la_base(anon_client, db):
    crear_usuario(db, role="hacker")

    r = login(anon_client, "juan", "clave-123456")

    assert r.status_code == 403
    assert r.get_json()["error"] == "Rol de usuario no válido"


@pytest.mark.parametrize("cuerpo", [
    {"username": 123, "password": "x"},
    {"username": ["a"], "password": "x"},
    {"username": "juan", "password": 123},
    {"username": "juan", "password": ["x"]},
])
def test_login_con_tipos_invalidos_da_400(anon_client, db, cuerpo):
    crear_usuario(db)

    r = anon_client.post(LOGIN, json=cuerpo)

    assert r.status_code == 400
    assert r.get_json()["error"] == "Formato de datos inválido"


# ================================================================ POST /register

def test_registro_crea_una_cuenta_pendiente_de_aprobacion(anon_client, db):
    r = anon_client.post(REGISTER, json={"username": "nuevo", "email": "nuevo@test.com",
                                         "password": "clave-123456"})

    assert r.status_code == 201
    assert r.get_json()["success"] is True
    email, role, status, application = fila(db, "nuevo")
    assert (email, role, status) == ("nuevo@test.com", ROLES.VENDOR, 0)
    assert application == Var.USER_APPLICATION_PENDING


def test_registro_guarda_la_contrasena_hasheada(anon_client, db):
    anon_client.post(REGISTER, json={"username": "nuevo", "email": "nuevo@test.com",
                                     "password": "clave-123456"})

    guardado = db.get_single_row("SELECT password FROM users WHERE username = 'nuevo'")[0]
    assert guardado != "clave-123456"
    assert check_password_hash(guardado, "clave-123456")


def test_registro_no_permite_elegirse_rol_ni_estado(anon_client, db):
    anon_client.post(REGISTER, json={"username": "nuevo", "email": "nuevo@test.com",
                                     "password": "clave-123456", "role": ROLES.ROOT, "status": 1,
                                     "application": Var.USER_APPLICATION_ACCEPTED})

    _, role, status, application = fila(db, "nuevo")
    assert (role, status, application) == (ROLES.VENDOR, 0, Var.USER_APPLICATION_PENDING)


def test_una_cuenta_recien_registrada_no_puede_loguearse_hasta_ser_aprobada(anon_client, db):
    anon_client.post(REGISTER, json={"username": "nuevo", "email": "nuevo@test.com",
                                     "password": "clave-123456"})

    assert login(anon_client, "nuevo", "clave-123456").status_code == 401


@pytest.mark.parametrize("faltante", ["username", "email", "password"])
def test_registro_sin_campos_requeridos(anon_client, db, faltante):
    cuerpo = {"username": "nuevo", "email": "nuevo@test.com", "password": "clave-123456"}
    del cuerpo[faltante]

    r = anon_client.post(REGISTER, json=cuerpo)

    assert r.status_code == 400
    assert r.get_json()["error"] == "Faltan campos requeridos"
    assert fila(db, "nuevo") is None


def test_registro_con_contrasena_corta(anon_client, db):
    r = anon_client.post(REGISTER, json={"username": "nuevo", "email": "nuevo@test.com", "password": "12345"})

    assert r.status_code == 400
    assert "mínimo 6" in r.get_json()["error"]
    assert fila(db, "nuevo") is None


def test_registro_con_email_invalido(anon_client, db):
    r = anon_client.post(REGISTER, json={"username": "nuevo", "email": "no-es-mail", "password": "clave-123456"})

    assert r.status_code == 400
    assert fila(db, "nuevo") is None


@pytest.mark.parametrize("username, email", [("juan", "otro@test.com"), ("otro", "juan@test.com")])
def test_registro_con_usuario_o_email_existente(anon_client, db, username, email):
    crear_usuario(db, "juan", "juan@test.com")

    r = anon_client.post(REGISTER, json={"username": username, "email": email, "password": "clave-123456"})

    assert r.status_code == 409
    assert r.get_json()["error"] == "Usuario o correo ya existe"


# ================================================================ GET /suggest/vendors

def test_sugerir_vendedores_sin_sesion_devuelve_401(anon_client):
    assert anon_client.get(SUGGEST, query_string={"q": "a"}).status_code == 401


@pytest.mark.parametrize("q", ["", "   "])
def test_sugerir_vendedores_con_busqueda_vacia(client, q):
    r = client.get(SUGGEST, query_string={"q": q})

    assert r.status_code == 200
    assert r.get_json() == {"data": []}


def test_sugerir_vendedores_incluye_vendedores_y_admins_activos(client, db):
    crear_usuario(db, "carlos", "carlos@test.com", role=ROLES.VENDOR)
    crear_usuario(db, "carla", "carla@test.com", role=ROLES.ADMIN)

    r = client.get(SUGGEST, query_string={"q": "carl"})

    assert {s["username"] for s in r.get_json()["data"]} == {"carlos", "carla"}
    assert set(r.get_json()["data"][0]) == {"id", "username", "email"}


def test_sugerir_vendedores_excluye_inactivos_y_root(client, db):
    crear_usuario(db, "carlos", "carlos@test.com", status=0)

    assert client.get(SUGGEST, query_string={"q": "carlos"}).get_json()["data"] == []
    assert client.get(SUGGEST, query_string={"q": "root"}).get_json()["data"] == []


def test_sugerir_vendedores_devuelve_como_maximo_10(client, db):
    for i in range(12):
        crear_usuario(db, f"vend{i:02d}", f"vend{i:02d}@test.com")

    assert len(client.get(SUGGEST, query_string={"q": "vend"}).get_json()["data"]) == 10


def test_un_vendedor_puede_usar_el_autocompletado(vendor_client):
    assert vendor_client.get(SUGGEST, query_string={"q": "x"}).status_code == 200


# ================================================================ recuperación de contraseña

def test_pedir_codigo_de_recuperacion(client, db, emails):
    crear_usuario(db)

    r = client.post(RESET, json={"email": "juan@test.com"})

    assert r.status_code == 200
    assert r.get_json()["message"] == "Codigo enviado al correo"
    codigo = db.get_reset_code("juan@test.com")[0]
    assert len(codigo) == 6 and codigo.isdigit()
    assert len(emails) == 1
    assert emails[0]["to"] == "juan@test.com"
    assert codigo in emails[0]["body"]


def test_pedir_codigo_de_un_email_inexistente(client, emails):
    r = client.post(RESET, json={"email": "nadie@test.com"})

    assert r.status_code == 404
    assert r.get_json()["error"] == "Usuario no encontrado"
    assert emails == []


def test_pedir_codigo_sin_email(client, emails):
    r = client.post(RESET, json={})

    assert r.status_code == 400
    assert emails == []


def test_pedir_codigo_con_formato_de_email_invalido(client, emails):
    r = client.post(RESET, json={"email": "no-es-mail"})

    assert r.status_code == 400
    assert emails == []


def test_pedir_codigo_sin_sesion_esta_permitido(anon_client, db, emails):
    """Es el flujo de 'olvidé mi contraseña': quien lo usa no puede tener sesión."""
    crear_usuario(db)

    r = anon_client.post(RESET, json={"email": "juan@test.com"})

    assert r.status_code == 200
    assert len(emails) == 1 and emails[0]["to"] == "juan@test.com"


def test_pedir_codigo_no_depende_de_ningun_permiso(vendor_client, db, sin_permisos, emails):
    crear_usuario(db)

    r = vendor_client.post(RESET, json={"email": "juan@test.com"})

    assert r.status_code == 200
    assert len(emails) == 1


def test_validar_codigo_correcto(anon_client, db):
    db.save_reset_code("juan@test.com", "123456")

    r = anon_client.post(VALIDATE, json={"email": "juan@test.com", "code": "123456"})

    assert r.status_code == 200


def test_validar_codigo_incorrecto(anon_client, db):
    db.save_reset_code("juan@test.com", "123456")

    r = anon_client.post(VALIDATE, json={"email": "juan@test.com", "code": "000000"})

    assert r.status_code == 401
    assert r.get_json()["error"] == "Código inválido o expirado"


def test_validar_codigo_de_otro_email(anon_client, db):
    db.save_reset_code("juan@test.com", "123456")

    r = anon_client.post(VALIDATE, json={"email": "otro@test.com", "code": "123456"})

    assert r.status_code == 401


def test_validar_codigo_expirado(anon_client, db):
    db.save_reset_code("juan@test.com", "123456")
    db.execute_query("UPDATE password_resets SET created_at = datetime('now', '-20 minutes')", fetch=False)

    r = anon_client.post(VALIDATE, json={"email": "juan@test.com", "code": "123456"})

    assert r.status_code == 401


@pytest.mark.parametrize("cuerpo", [{}, {"email": "juan@test.com"}, {"code": "123456"}])
def test_validar_codigo_con_campos_faltantes(anon_client, cuerpo):
    r = anon_client.post(VALIDATE, json=cuerpo)

    assert r.status_code == 400
    assert r.get_json()["error"] == "Faltan campos requeridos"


def test_cambiar_contrasena_con_codigo_valido(anon_client, db):
    crear_usuario(db)
    db.save_reset_code("juan@test.com", "123456")

    r = anon_client.post(CHANGE, json={"email": "juan@test.com", "code": "123456",
                                       "new_password": "nueva-clave-9"})

    assert r.status_code == 200
    assert r.get_json()["message"] == "Contraseña restablecida exitosamente"
    assert login(anon_client, "juan", "nueva-clave-9").status_code == 200
    assert login(anon_client, "juan", "clave-123456").status_code == 401


def test_el_codigo_se_consume_y_no_sirve_dos_veces(anon_client, db):
    crear_usuario(db)
    db.save_reset_code("juan@test.com", "123456")
    cuerpo = {"email": "juan@test.com", "code": "123456", "new_password": "nueva-clave-9"}
    anon_client.post(CHANGE, json=cuerpo)

    r = anon_client.post(CHANGE, json={**cuerpo, "new_password": "otra-clave-9"})

    assert r.status_code == 401
    assert db.get_reset_code("juan@test.com") == (None, None)
    assert login(anon_client, "juan", "nueva-clave-9").status_code == 200


def test_cambiar_contrasena_con_codigo_incorrecto(anon_client, db):
    uid = crear_usuario(db)
    antes = hash_de(db, uid)
    db.save_reset_code("juan@test.com", "123456")

    r = anon_client.post(CHANGE, json={"email": "juan@test.com", "code": "000000",
                                       "new_password": "nueva-clave-9"})

    assert r.status_code == 401
    assert hash_de(db, uid) == antes


def test_cambiar_contrasena_con_codigo_expirado(anon_client, db):
    uid = crear_usuario(db)
    antes = hash_de(db, uid)
    db.save_reset_code("juan@test.com", "123456")
    db.execute_query("UPDATE password_resets SET created_at = datetime('now', '-20 minutes')", fetch=False)

    r = anon_client.post(CHANGE, json={"email": "juan@test.com", "code": "123456",
                                       "new_password": "nueva-clave-9"})

    assert r.status_code == 401
    assert hash_de(db, uid) == antes


def test_el_codigo_de_un_usuario_no_sirve_para_cambiar_la_clave_de_otro(anon_client, db):
    crear_usuario(db, "juan", "juan@test.com")
    victima = crear_usuario(db, "ana", "ana@test.com")
    antes = hash_de(db, victima)
    db.save_reset_code("juan@test.com", "123456")

    r = anon_client.post(CHANGE, json={"email": "ana@test.com", "code": "123456",
                                       "new_password": "hackeada-123"})

    assert r.status_code == 401
    assert hash_de(db, victima) == antes


def test_cambiar_contrasena_sin_nueva_contrasena(anon_client, db):
    crear_usuario(db)
    db.save_reset_code("juan@test.com", "123456")

    r = anon_client.post(CHANGE, json={"email": "juan@test.com", "code": "123456"})

    assert r.status_code == 400
    assert r.get_json()["error"] == "Faltan campos requeridos"


@pytest.mark.parametrize("clave", ["12", "12345", "   "])
def test_cambiar_contrasena_a_una_demasiado_corta_da_400(anon_client, db, clave):
    uid = crear_usuario(db)
    antes = hash_de(db, uid)
    db.save_reset_code("juan@test.com", "123456")

    r = anon_client.post(CHANGE, json={"email": "juan@test.com", "code": "123456", "new_password": clave})

    assert r.status_code == 400
    assert hash_de(db, uid) == antes


def test_cambiar_contrasena_a_una_de_exactamente_6_caracteres(anon_client, db):
    crear_usuario(db)
    db.save_reset_code("juan@test.com", "123456")

    r = anon_client.post(CHANGE, json={"email": "juan@test.com", "code": "123456", "new_password": "123456"})

    assert r.status_code == 200