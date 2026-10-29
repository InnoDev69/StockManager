"""
Tests de CreditMixin: alta, lectura, listado y actualización de clientes.
(Los saldos, pagos, ajustes y límites de crédito ya los cubre test_credit.py.)
"""
import pytest

from core.bd.bdErrors import DatabaseError

ROOT_ID = 1   # init_db crea el usuario root con id 1


@pytest.fixture
def cliente(db):
    return db.create_customer("Ana", "111", 500)


def limite(db, cliente_id):
    return db.get_customer(cliente_id)[3]


# ---------- create / get ----------

def test_crear_cliente_guarda_los_datos(db):
    cid = db.create_customer("Ana", "111", 500)

    assert db.get_customer(cid) == (cid, "Ana", "111", 500.0, 1)


def test_crear_cliente_solo_con_nombre(db):
    cid = db.create_customer("Beto")

    assert db.get_customer(cid) == (cid, "Beto", None, None, 1)


def test_get_customer_inexistente_devuelve_none(db):
    assert db.get_customer(99999) is None


# ---------- update_customer ----------

def test_update_cambia_nombre_y_telefono(db, cliente):
    db.update_customer(cliente, name="Ana María", phone="222")

    assert db.get_customer(cliente)[1:3] == ("Ana María", "222")
    assert limite(db, cliente) == 500.0


def test_update_cambia_el_limite(db, cliente):
    db.update_customer(cliente, credit_limit=900, update_credit_limit=True)

    assert limite(db, cliente) == 900.0


def test_update_con_limite_y_sin_el_flag_tambien_lo_cambia(db, cliente):
    """Compatibilidad: llamar con credit_limit=<valor> sin el flag sigue funcionando."""
    db.update_customer(cliente, credit_limit=900)

    assert limite(db, cliente) == 900.0


def test_update_con_flag_y_limite_none_quita_el_limite(db, cliente):
    db.update_customer(cliente, credit_limit=None, update_credit_limit=True)

    assert limite(db, cliente) is None


def test_update_sin_flag_y_limite_none_no_toca_el_limite(db, cliente):
    db.update_customer(cliente, name="Otra")

    assert limite(db, cliente) == 500.0


def test_update_solo_el_limite_no_toca_el_resto(db, cliente):
    db.update_customer(cliente, credit_limit=None, update_credit_limit=True)

    assert db.get_customer(cliente)[1:3] == ("Ana", "111")


def test_update_puede_deshabilitar_al_cliente(db, cliente):
    db.update_customer(cliente, status=0)

    assert db.get_customer(cliente)[4] == 0


def test_update_sin_ningun_campo_falla(db, cliente):
    with pytest.raises(DatabaseError, match="No se proporcionaron campos"):
        db.update_customer(cliente)


def test_update_de_un_cliente_inexistente_no_falla_ni_crea_nada(db):
    db.update_customer(99999, name="X")

    assert db.get_customer(99999) is None


# ---------- listados ----------

def test_list_customers_with_balance_incluye_clientes_sin_movimientos(db):
    db.create_customer("Ana")

    filas = db.list_customers_with_balance()

    assert [(f[1], f[5]) for f in filas] == [("Ana", 0)]


def test_list_customers_with_balance_suma_deuda_pagos_y_ajustes(db, cliente):
    db.register_adjustment(cliente, 100, ROOT_ID, "saldo inicial")
    db.register_payment(cliente, 30, ROOT_ID)

    filas = db.list_customers_with_balance()

    assert filas[0][5] == 70


def test_list_customers_with_balance_oculta_deshabilitados_y_filtra(db):
    ana = db.create_customer("Ana")
    db.create_customer("Beto")
    db.update_customer(ana, status=0)

    assert [f[1] for f in db.list_customers_with_balance()] == ["Beto"]
    assert db.list_customers_with_balance(search="zzz") == []
    assert [f[1] for f in db.list_customers_with_balance(search="bet")] == ["Beto"]


def test_list_customers_ordena_por_nombre(db):
    db.create_customer("Carla")
    db.create_customer("Ana")

    assert [f[1] for f in db.list_customers()] == ["Ana", "Carla"]


def test_movimientos_respeta_el_limite(db, cliente):
    for _ in range(3):
        db.register_adjustment(cliente, 10, ROOT_ID, "x")

    assert len(db.get_customer_movements(cliente, limit=2)) == 2