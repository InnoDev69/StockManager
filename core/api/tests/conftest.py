"""
Fixtures para los tests de la API.

Aislamiento: todo lo que la app escribe (base de datos, config.json, sesiones de
Flask) va a una carpeta temporal. Estos tests NUNCA tocan tu base real.
Para lograrlo, get_data_path se reemplaza ANTES de importar nada de 'core'.
"""
import os
import pathlib
import sys
import tempfile

import pytest

# ------------------------------------------------------------------
# 1) Redirigir los datos de la app a una carpeta temporal
# ------------------------------------------------------------------
_DATA_DIR = pathlib.Path(tempfile.mkdtemp(prefix="stockly_tests_"))

os.environ["FLASK_SECRET_KEY"] = "clave-solo-para-tests"   # evita escribir 'app.secret_key' en el config real
os.environ["DB_NAME"] = "sesion_tests.db"                  # nombre de la base global de la sesión de tests


def _tmp_data_path(*args, **kwargs):
    """Reemplazo de get_data_path: misma idea, pero dentro de la carpeta temporal."""
    sub = args[0] if args else (kwargs.get("path") or kwargs.get("archive") or "")
    target = _DATA_DIR / sub if sub else _DATA_DIR
    target.parent.mkdir(parents=True, exist_ok=True)
    return str(target)


import miscellaneous            # noqa: E402
import miscellaneous.dirs       # noqa: E402

miscellaneous.get_data_path = _tmp_data_path
miscellaneous.dirs.get_data_path = _tmp_data_path

# ------------------------------------------------------------------
# 2) Recién ahora se importa la app (bdInstance crea su base global acá)
# ------------------------------------------------------------------
from core.bd import bdInstance                 # noqa: E402
from core.bd.bdConector import BDConector      # noqa: E402

_SESSION_DB = bdInstance.db

# Seguro anti-desastres: si la base global no quedó en la carpeta temporal, se corta todo.
if not os.path.abspath(_SESSION_DB.db_path).startswith(str(_DATA_DIR)):
    pytest.exit(
        f"Los tests quedarían usando una base fuera de la carpeta temporal: {_SESSION_DB.db_path}. "
        "Revisá cómo get_data_path arma las rutas.",
        returncode=2,
    )

ROOT_ID = 1   # init_db crea el usuario root con id 1


# ------------------------------------------------------------------
# 3) Fixtures
# ------------------------------------------------------------------
@pytest.fixture
def db(tmp_path, monkeypatch):
    """
    Base de datos limpia para cada test. Los módulos de la API hicieron
    'from core.bd.bdInstance import db' al importarse, así que se reemplaza esa
    referencia en todos los que la tengan.
    """
    conn = BDConector(db_path=str(tmp_path / "test.db"))
    conn.init_db()
    for name, module in list(sys.modules.items()):
        if module is not None and name.split(".")[0] in ("core", "miscellaneous"):
            if getattr(module, "db", None) is _SESSION_DB:
                monkeypatch.setattr(module, "db", conn)
    yield conn
    conn.close_conn()


@pytest.fixture(scope="session")
def app():
    from core.stockly import Stockly
    return Stockly().app


def _login(client, user_id, role):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["role"] = role
    return client


@pytest.fixture
def client(app, db):
    """Cliente con sesión iniciada como root (tiene todos los permisos)."""
    return _login(app.test_client(), ROOT_ID, "root")


@pytest.fixture
def vendor_client(app, db):
    """Cliente con sesión de vendedor (sin permisos de admin)."""
    db.add_user("vendedor1", "clave-123456", "vendedor1@test.com", role="vendedor", status=1)
    vendor_id = db.get_single_row("SELECT id FROM users WHERE username = 'vendedor1'")[0]
    return _login(app.test_client(), vendor_id, "vendedor")


@pytest.fixture
def anon_client(app, db):
    """Cliente sin sesión."""
    return app.test_client()


@pytest.fixture
def item(db):
    """Producto normal de $80 con stock 10. Devuelve su id."""
    db.add_item("111", "", "Yerba", 10, 2, None, 80.0)
    return db.get_single_row("SELECT id FROM items WHERE barrs_code='111'")[0]


@pytest.fixture
def generic_item(db):
    """Producto en blanco: sin control de stock y con precio libre. Devuelve su id."""
    db.add_item("GEN", "", "Varios", 0, 5, None, 0.0, track_stock=0, allow_custom_price=1)
    return db.get_single_row("SELECT id FROM items WHERE barrs_code='GEN'")[0]