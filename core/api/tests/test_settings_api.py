"""
Tests de la API de ajustes (core/api/settings_api.py):
perfil, cambio de contraseña y configuración de la aplicación.

La configuración real (config.json) NO se toca: se reemplaza por un config en memoria.
Los tests con xfail(strict=True) (si queda alguno) documentan problemas reales del código
actual; el motivo está en cada marcador.
"""
import sys

import pytest
from werkzeug.security import check_password_hash, generate_password_hash

from core.bd.bdErrors import ConfigurationError
from miscellaneous import ROLES, Var

PROFILE = "/api/settings/profile"
PASSWORD = "/api/settings/password"
SETTINGS = "/api/settings/actual"
LOGIN = "/api/login"


# ---------------------------------------------------------------- helpers y fixtures

class ConfigFalso:
    """
    Config en memoria con la misma interfaz que usa settings_api.

    Como el Config real, set() lanza ConfigurationError para las claves ignoradas
    ("app" y "ui"); la vista lo traduce a 403. (El real, además, ya modificó el valor en
    memoria antes de lanzar; acá no, porque estos tests prueban la vista y no el Config.)
    """

    IGNORADAS = ("app", "ui")

    def __init__(self, inicial=None):
        self.datos = dict(inicial or {})

    def get_all(self, exclude=None):
        return {k: v for k, v in self.datos.items() if k not in (exclude or [])}

    def get(self, key, exclude=None):
        if key in (exclude or []):
            return None
        return self.datos.get(key)

    def set(self, key, value):
        if key.split(".")[0] in self.IGNORADAS:
            raise ConfigurationError
        self.datos[key] = value


@pytest.fixture
def config(monkeypatch):
    falso = ConfigFalso({"app": {"secret": "no-mostrar"}, "ui": {"tema": "oscuro"},
                         "moneda": "ARS", "iva": 21})
    monkeypatch.setattr(sys.modules["core.api.settings_api"], "config", falso)
    return falso


def crear_usuario(db, username="juan", email="juan@test.com", password="clave-123456", role=ROLES.VENDOR):
    db.add_user(username, generate_password_hash(password), email, role=role, status=1,
                application=Var.USER_APPLICATION_ACCEPTED)
    return db.get_single_row("SELECT id FROM users WHERE username = ?", (username,))[0]


@pytest.fixture
def sin_permisos(monkeypatch):
    """Ningún rol (salvo root, que siempre pasa) tiene permisos: no depende de la config de roles."""
    monkeypatch.setattr("core.services.permissions_service.has_permission", lambda *a, **k: False)


@pytest.fixture
def con_todos_los_permisos(monkeypatch):
    monkeypatch.setattr("core.services.permissions_service.has_permission", lambda *a, **k: True)


@pytest.fixture
def usuario(app, db):
    """(client con sesión de 'juan', id de juan). Su contraseña real es 'clave-123456'."""
    uid = crear_usuario(db)
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["user_id"] = uid
        sess["role"] = ROLES.VENDOR
    return c, uid


def email_de(db, user_id):
    return db.get_single_row("SELECT email FROM users WHERE id = ?", (user_id,))[0]


def hash_de(db, user_id):
    return db.get_single_row("SELECT password FROM users WHERE id = ?", (user_id,))[0]


def cambio(actual="clave-123456", nueva="nueva-clave-9", confirmar=None):
    return {"current_password": actual, "new_password": nueva,
            "confirm_password": nueva if confirmar is None else confirmar}


# ================================================================ PUT /settings/profile

def test_actualizar_el_email_del_perfil(usuario, db):
    c, uid = usuario

    r = c.put(PROFILE, json={"email": "nuevo@test.com"})

    assert r.status_code == 200
    assert r.get_json()["success"] is True
    assert email_de(db, uid) == "nuevo@test.com"


def test_actualizar_el_perfil_recorta_espacios(usuario, db):
    c, uid = usuario

    c.put(PROFILE, json={"email": "  nuevo@test.com  "})

    assert email_de(db, uid) == "nuevo@test.com"


def test_actualizar_el_perfil_solo_modifica_al_usuario_de_la_sesion(usuario, db):
    c, uid = usuario
    otro = crear_usuario(db, "ana", "ana@test.com")

    c.put(PROFILE, json={"email": "nuevo@test.com"})

    assert email_de(db, otro) == "ana@test.com"
    assert email_de(db, 1) != "nuevo@test.com"      # root


@pytest.mark.parametrize("cuerpo", [{}, {"email": ""}, {"email": "   "}])
def test_actualizar_el_perfil_sin_email(usuario, db, cuerpo):
    c, uid = usuario

    r = c.put(PROFILE, json=cuerpo)

    assert r.status_code == 400
    assert r.get_json()["error"] == "Email es requerido"
    assert email_de(db, uid) == "juan@test.com"


@pytest.mark.parametrize("email", ["sin-arroba.com", "sin@punto", "plano"])
def test_actualizar_el_perfil_con_email_invalido(usuario, db, email):
    c, uid = usuario

    r = c.put(PROFILE, json={"email": email})

    assert r.status_code == 400
    assert r.get_json()["error"] == "Email inválido"
    assert email_de(db, uid) == "juan@test.com"


@pytest.mark.parametrize("email", ["@.", ".@", "a@b.", "@b.com", "a b@c.com"])
def test_actualizar_el_perfil_con_email_absurdo(usuario, db, email):
    c, uid = usuario

    r = c.put(PROFILE, json={"email": email})

    assert r.status_code == 400
    assert r.get_json()["error"] == "Email inválido"
    assert email_de(db, uid) == "juan@test.com"


def test_actualizar_el_perfil_con_email_de_otro_usuario_da_409(usuario, db):
    c, uid = usuario
    crear_usuario(db, "ana", "ana@test.com")

    r = c.put(PROFILE, json={"email": "ana@test.com"})

    assert r.status_code == 409
    assert email_de(db, uid) == "juan@test.com"


def test_actualizar_el_perfil_sin_sesion_devuelve_401(anon_client):
    assert anon_client.put(PROFILE, json={"email": "x@test.com"}).status_code == 401


# ================================================================ PUT /settings/password

def test_cambiar_la_contrasena(usuario, db, anon_client):
    c, uid = usuario

    r = c.put(PASSWORD, json=cambio())

    assert r.status_code == 200
    assert r.get_json()["success"] is True
    assert hash_de(db, uid) != "nueva-clave-9"
    assert check_password_hash(hash_de(db, uid), "nueva-clave-9")
    assert anon_client.post(LOGIN, json={"username": "juan", "password": "nueva-clave-9"}).status_code == 200
    assert anon_client.post(LOGIN, json={"username": "juan", "password": "clave-123456"}).status_code == 401


def test_cambiar_la_contrasena_solo_modifica_al_usuario_de_la_sesion(usuario, db):
    c, uid = usuario
    otro = crear_usuario(db, "ana", "ana@test.com")
    antes_otro, antes_root = hash_de(db, otro), hash_de(db, 1)

    c.put(PASSWORD, json=cambio())

    assert hash_de(db, otro) == antes_otro
    assert hash_de(db, 1) == antes_root


def test_cambiar_la_contrasena_con_la_actual_incorrecta(usuario, db):
    c, uid = usuario
    antes = hash_de(db, uid)

    r = c.put(PASSWORD, json=cambio(actual="no-es-esta"))

    assert r.status_code == 401
    assert r.get_json()["error"] == "Contraseña actual incorrecta"
    assert hash_de(db, uid) == antes


def test_cambiar_la_contrasena_si_las_nuevas_no_coinciden(usuario, db):
    c, uid = usuario
    antes = hash_de(db, uid)

    r = c.put(PASSWORD, json=cambio(nueva="nueva-clave-9", confirmar="distinta-9"))

    assert r.status_code == 400
    assert r.get_json()["error"] == "Las contraseñas nuevas no coinciden"
    assert hash_de(db, uid) == antes


def test_cambiar_la_contrasena_a_una_corta(usuario, db):
    c, uid = usuario
    antes = hash_de(db, uid)

    r = c.put(PASSWORD, json=cambio(nueva="12345"))

    assert r.status_code == 400
    assert r.get_json()["error"] == "La contraseña debe tener al menos 6 caracteres"
    assert hash_de(db, uid) == antes


def test_cambiar_la_contrasena_a_una_de_exactamente_6_caracteres(usuario, db):
    c, uid = usuario

    assert c.put(PASSWORD, json=cambio(nueva="123456")).status_code == 200


@pytest.mark.parametrize("faltante", ["current_password", "new_password", "confirm_password"])
def test_cambiar_la_contrasena_con_campos_faltantes(usuario, db, faltante):
    c, uid = usuario
    cuerpo = cambio()
    del cuerpo[faltante]
    antes = hash_de(db, uid)

    r = c.put(PASSWORD, json=cuerpo)

    assert r.status_code == 400
    assert r.get_json()["error"] == "Todos los campos son requeridos"
    assert hash_de(db, uid) == antes


def test_cambiar_la_contrasena_sin_sesion_devuelve_401(anon_client):
    assert anon_client.put(PASSWORD, json=cambio()).status_code == 401


# ================================================================ GET /settings/actual

def test_obtener_toda_la_configuracion_oculta_app_y_ui(client, config):
    r = client.get(SETTINGS)

    assert r.status_code == 200
    assert r.get_json() == {"moneda": "ARS", "iva": 21}


def test_obtener_la_configuracion_decodifica_los_roles(client, config):
    client.put(f"{SETTINGS}/roles", json={"value": "admin,vendedor"})

    r = client.get(SETTINGS)

    assert r.get_json()["roles"] == "admin,vendedor"


def test_obtener_toda_la_configuracion_sin_sesion_devuelve_401(anon_client, config):
    assert anon_client.get(SETTINGS).status_code == 401


def test_obtener_una_configuracion(client, config):
    r = client.get(f"{SETTINGS}/moneda")

    assert r.status_code == 200
    assert r.get_json() == {"moneda": "ARS"}


def test_obtener_una_configuracion_inexistente(client, config):
    r = client.get(f"{SETTINGS}/no_existe")

    assert r.status_code == 404
    assert r.get_json()["success"] is False


@pytest.mark.parametrize("clave", ["app", "ui"])
def test_las_claves_excluidas_no_se_pueden_leer(client, config, clave):
    assert client.get(f"{SETTINGS}/{clave}").status_code == 404


def test_obtener_una_configuracion_sin_sesion_devuelve_401(anon_client, config):
    assert anon_client.get(f"{SETTINGS}/moneda").status_code == 401


# ================================================================ PUT /settings/actual/<key>

def test_actualizar_una_configuracion(client, config):
    r = client.put(f"{SETTINGS}/moneda", json={"value": "USD"})

    assert r.status_code == 200
    assert r.get_json()["data"] == {"moneda": "USD"}
    assert config.datos["moneda"] == "USD"
    assert client.get(f"{SETTINGS}/moneda").get_json() == {"moneda": "USD"}


@pytest.mark.parametrize("valor", [0, False, ""])
def test_actualizar_una_configuracion_con_valores_falsy_pero_validos(client, config, valor):
    r = client.put(f"{SETTINGS}/iva", json={"value": valor})

    assert r.status_code == 200
    assert config.datos["iva"] == valor


@pytest.mark.parametrize("cuerpo", [{}, {"value": None}, {"otro": 1}])
def test_actualizar_una_configuracion_sin_valor(client, config, cuerpo):
    r = client.put(f"{SETTINGS}/moneda", json=cuerpo)

    assert r.status_code == 400
    assert r.get_json()["error"] == "El valor es requerido"
    assert config.datos["moneda"] == "ARS"


def test_actualizar_los_roles_los_guarda_codificados(client, config):
    r = client.put(f"{SETTINGS}/roles", json={"value": "admin,vendedor"})

    assert r.status_code == 200
    assert config.datos["roles"] != "admin,vendedor"      # se guardó codificado
    assert client.get(f"{SETTINGS}/roles").get_json() == {"roles": "admin,vendedor"}


def test_actualizar_una_configuracion_sin_sesion_devuelve_401(anon_client, config):
    r = anon_client.put(f"{SETTINGS}/moneda", json={"value": "USD"})

    assert r.status_code == 401
    assert config.datos["moneda"] == "ARS"


def test_cambiar_la_configuracion_sin_permiso_devuelve_403(vendor_client, config, sin_permisos):
    r = vendor_client.put(f"{SETTINGS}/moneda", json={"value": "USD"})

    assert r.status_code == 403
    assert config.datos["moneda"] == "ARS"


def test_cambiar_los_roles_sin_permiso_devuelve_403(vendor_client, config, sin_permisos):
    r = vendor_client.put(f"{SETTINGS}/roles", json={"value": "todos-son-admin"})

    assert r.status_code == 403
    assert "roles" not in config.datos


def test_cambiar_la_configuracion_con_el_permiso_funciona(vendor_client, config, con_todos_los_permisos):
    r = vendor_client.put(f"{SETTINGS}/moneda", json={"value": "USD"})

    assert r.status_code == 200
    assert config.datos["moneda"] == "USD"


@pytest.mark.parametrize("clave", ["app", "ui"])
def test_las_claves_excluidas_no_se_pueden_escribir(client, config, clave):
    r = client.put(f"{SETTINGS}/{clave}", json={"value": "pisado"})

    assert r.status_code == 403
    assert r.get_json()["success"] is False
    assert clave in r.get_json()["error"]