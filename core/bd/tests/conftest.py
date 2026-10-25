# tests/conftest.py
import pytest
from core.bd.bdConector import BDConector

@pytest.fixture
def db(tmp_path):
    """Fixture para crear una base de datos de prueba."""
    conn = BDConector(db_path=str(tmp_path / "test.db"))
    conn.init_db()
    yield conn
    conn.close_conn()