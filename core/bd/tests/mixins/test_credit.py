import pytest

from core.bd.bdErrors import (
    DatabaseError,
    CreditLimitExceededError,
    InsufficientBalanceError,
)

ROOT_ID = 1          # init_db crea el usuario root con id 1
FECHA = "2026-10-16"


@pytest.fixture
def item(db):
    """Producto de $80 con stock 10. Devuelve su id."""
    db.add_item("111", "", "Yerba", 10, 2, None, 80.0)
    return db.get_single_row("SELECT id FROM items WHERE barrs_code='111'")[0]


@pytest.fixture
def cliente(db):
    """Cliente sin límite de crédito."""
    return db.create_customer("Ana")


def vender_fiado(db, item, cliente, cantidad=1, **kwargs):
    return db.create_mixed_sale(
        FECHA, ROOT_ID,
        unit_lines=[{"item_id": item, "quantity": cantidad}],
        payment_method="Fiado",
        customer_id=cliente,
        **kwargs,
    )


# ---------- Saldo ----------

def test_cliente_nuevo_tiene_saldo_cero(db, cliente):
    assert db.get_customer_balance(cliente) == 0


def test_venta_fiada_genera_deuda_por_el_total(db, item, cliente):
    vender_fiado(db, item, cliente, cantidad=2)
    assert db.get_customer_balance(cliente) == 160


def test_pago_reduce_el_saldo(db, item, cliente):
    vender_fiado(db, item, cliente)
    db.register_payment(cliente, 30, ROOT_ID)
    assert db.get_customer_balance(cliente) == 50


def test_ajuste_positivo_y_negativo(db, cliente):
    db.register_adjustment(cliente, 100, ROOT_ID, "saldo inicial")
    db.register_adjustment(cliente, -40, ROOT_ID, "descuento")
    assert db.get_customer_balance(cliente) == 60


# ---------- Validaciones de pagos y ajustes ----------

def test_pago_mayor_al_saldo_falla(db, item, cliente):
    vender_fiado(db, item, cliente)
    with pytest.raises(InsufficientBalanceError):
        db.register_payment(cliente, 81, ROOT_ID)
    assert db.get_customer_balance(cliente) == 80


@pytest.mark.parametrize("monto", [0, -5])
def test_pago_no_positivo_falla(db, item, cliente, monto):
    vender_fiado(db, item, cliente)
    with pytest.raises(ValueError):
        db.register_payment(cliente, monto, ROOT_ID)


@pytest.mark.parametrize("nota", [None, ""])
def test_ajuste_sin_nota_falla(db, cliente, nota):
    with pytest.raises(DatabaseError):
        db.register_adjustment(cliente, 10, ROOT_ID, nota)


# ---------- Límite de crédito ----------

def test_venta_sobre_el_limite_falla_y_revierte_todo(db, item):
    limitado = db.create_customer("Beto", credit_limit=100)
    with pytest.raises(CreditLimitExceededError):
        vender_fiado(db, item, limitado, cantidad=2)  # 160 > 100

    assert db.get_count("SELECT COUNT(*) FROM sells") == 0
    assert db.get_single_row("SELECT quantity FROM items WHERE id=?", (item,))[0] == 10
    assert db.get_customer_balance(limitado) == 0


def test_venta_sobre_el_limite_pasa_con_force_credit(db, item):
    limitado = db.create_customer("Beto", credit_limit=100)
    vender_fiado(db, item, limitado, cantidad=2, force_credit=True)
    assert db.get_customer_balance(limitado) == 160


def test_el_limite_considera_la_deuda_previa(db, item):
    limitado = db.create_customer("Beto", credit_limit=100)
    vender_fiado(db, item, limitado)              # deuda 80
    with pytest.raises(CreditLimitExceededError):
        vender_fiado(db, item, limitado)          # 80 + 80 > 100


# ---------- Pago mixto y datos inconsistentes ----------

def test_venta_mixta_fia_solo_la_diferencia(db, item, cliente):
    db.create_mixed_sale(
        FECHA, ROOT_ID,
        unit_lines=[{"item_id": item, "quantity": 1}],
        payment_method="Mixto", customer_id=cliente, amount_paid=50,
    )
    assert db.get_customer_balance(cliente) == 30


@pytest.mark.parametrize("pagado", [None, 0, 80, 100])
def test_mixto_con_monto_invalido_falla(db, item, cliente, pagado):
    with pytest.raises(ValueError):
        db.create_mixed_sale(
            FECHA, ROOT_ID,
            unit_lines=[{"item_id": item, "quantity": 1}],
            payment_method="Mixto", customer_id=cliente, amount_paid=pagado,
        )


def test_fiado_sin_cliente_falla(db, item):
    with pytest.raises(ValueError):
        db.create_mixed_sale(
            FECHA, ROOT_ID,
            unit_lines=[{"item_id": item, "quantity": 1}],
            payment_method="Fiado",
        )