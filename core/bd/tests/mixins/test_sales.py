import pytest

from core.bd.bdErrors import (
    DatabaseError,
    CreditLimitExceededError,
    InsufficientBalanceError,
    InsufficientStockError,
)

ROOT_ID = 1          # init_db crea el usuario root con id 1
DATE = "2026-10-16"

@pytest.fixture
def item(db):
    """Producto de $80 con stock 10. Devuelve su id."""
    db.add_item("111", "", "Yerba", 10, 2, None, 80.0)
    return db.get_single_row("SELECT id FROM items WHERE barrs_code='111'")[0]

@pytest.fixture
def weight_item(db):
    """$80 cada 500 g, con 5000 g en stock. Devuelve el id en weight_items."""
    return db.add_weight_item("Jamón", 5000, 80.0, 500)

# Tests

def test_stock_insuficiente(db, item):
    """No se puede vender más de lo que hay en stock."""
    with pytest.raises(InsufficientStockError):
        db.create_mixed_sale(
            DATE, ROOT_ID,
            unit_lines=[{"item_id": item, "quantity": 20}],
            payment_method="Efectivo",
        )
        
def test_product_null(db):
    """Producto inexistente y lista de ítems vacía."""
    with pytest.raises(DatabaseError):
        db.create_mixed_sale(
            DATE, ROOT_ID,
            unit_lines=[{"item_id": 9999, "quantity": 1}],
            payment_method="Efectivo",
        )
    with pytest.raises(ValueError):
        db.create_mixed_sale(
            DATE, ROOT_ID,
            unit_lines=[],
            payment_method="Efectivo",
        )
        
def test_update_sale(db, item):
    """update_sale devuelve el stock de las líneas viejas y descuenta el de las nuevas"""
    # Venta inicial: 2 unidades
    sale_id = db.create_mixed_sale(
        DATE, ROOT_ID,
        unit_lines=[{"item_id": item, "quantity": 2}],
        payment_method="Efectivo",
    )
    assert db.get_item_stock(item) == 8

    # Actualización: 5 unidades (debe devolver 2 y descontar 5)
    db.update_sale(
        sale_id,
        items=[{"item_id": item, "quantity": 5}],
        vendor_id=ROOT_ID,
        payment_method="Efectivo",
        user_id=ROOT_ID,
    )
    assert db.get_item_stock(item) == 5

def total_desde_lineas(lines):
    """details.price es unitario; weight_details.price ya es el total de la línea."""
    total = 0.0
    for _sell_id, _name, sale_type, amount, price in lines:
        total += amount * price if sale_type == "unit" else price
    return round(total, 2)

def test_total_equals_sale_lines(db, item):
    """get_sale_total coincide con la suma de get_sale_lines"""
    sale_id = db.create_mixed_sale(
        DATE, ROOT_ID,
        unit_lines=[{"item_id": item, "quantity": 3}],
        payment_method="Efectivo",
    )
    lines = db.get_sale_lines(sale_id)

    assert total_desde_lineas(lines) == 240.0
    assert db.get_sale_total(sale_id) == 240.0
    
def test_mixed_sale(db, item, weight_item):
    """Venta mixta con productos por unidad y por peso a la vez"""
    cliente = db.create_customer("Ana")
    sale_id = db.create_mixed_sale(
        DATE, ROOT_ID,
        unit_lines=[{"item_id": item, "quantity": 2}],         # 2 x 80   = 160
        weight_lines=[{"weight_item_id": weight_item, "weight": 250}],  # 250 g = 40
        payment_method="Mixto",
        customer_id=cliente,
        amount_paid=100,
    )
    lines = db.get_sale_lines(sale_id)

    assert total_desde_lineas(lines) == 200.0
    assert db.get_sale_total(sale_id) == 200.0
    assert db.get_customer_balance(cliente) == 100.0   # fiado: 200 - 100
    assert db.get_single_row(
        "SELECT weight FROM weight_items WHERE id=?", (weight_item,)
    )[0] == 4750