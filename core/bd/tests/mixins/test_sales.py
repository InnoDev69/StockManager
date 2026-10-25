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

@pytest.fixture
def generic_item(db):
    """Producto en blanco: sin control de stock y con precio libre. Devuelve su id."""
    db.add_item("GEN", "", "Varios", 0, 5, None, 0.0, track_stock=0, allow_custom_price=1)
    return db.get_single_row("SELECT id FROM items WHERE barrs_code='GEN'")[0]

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

def test_generico_visible_en_listados(db, generic_item):
    """El genérico se puede buscar y listar: solo se excluye de las alertas de stock."""
    assert db.get_item_by_id(generic_item) is not None
    assert any(i["id"] == generic_item for i in db.get_all_items())

def test_generico_vende_sin_stock(db, generic_item):
    """Se puede vender con stock 0, no toca la cantidad y el total usa el precio de la línea."""
    sale_id = db.create_mixed_sale(
        DATE, ROOT_ID,
        unit_lines=[{"item_id": generic_item, "quantity": 3, "price": 150.0}],
        payment_method="Efectivo",
    )
    assert db.get_item_stock(generic_item) == 0
    assert db.get_sale_total(sale_id) == 450.0


def test_generico_exige_precio(db, generic_item):
    """Sin precio, o con precio <= 0, falla y no deja ninguna venta registrada."""
    for line in (
        {"item_id": generic_item, "quantity": 1},
        {"item_id": generic_item, "quantity": 1, "price": 0},
        {"item_id": generic_item, "quantity": 1, "price": -5},
    ):
        with pytest.raises(ValueError):
            db.create_mixed_sale(DATE, ROOT_ID, unit_lines=[line], payment_method="Efectivo")

    # El rollback de la transacción no debe dejar ventas a medias
    assert db.get_count("SELECT COUNT(*) FROM sells") == 0


def test_producto_normal_ignora_precio_de_la_linea(db, item):
    """Regresión: el precio enviado desde afuera solo vale para productos con precio libre."""
    sale_id = db.create_mixed_sale(
        DATE, ROOT_ID,
        unit_lines=[{"item_id": item, "quantity": 1, "price": 1.0}],
        payment_method="Efectivo",
    )
    assert db.get_sale_total(sale_id) == 80.0


def test_venta_con_generico_y_normal(db, item, generic_item):
    """En una misma venta, el normal descuenta stock y el genérico no."""
    sale_id = db.create_mixed_sale(
        DATE, ROOT_ID,
        unit_lines=[
            {"item_id": item, "quantity": 2},                          # 160
            {"item_id": generic_item, "quantity": 1, "price": 500.0},  # 500
        ],
        payment_method="Efectivo",
    )
    assert db.get_item_stock(item) == 8
    assert db.get_item_stock(generic_item) == 0
    assert db.get_sale_total(sale_id) == 660.0


def test_update_sale_no_inventa_stock_en_generico(db, generic_item):
    """Al editar una venta, el genérico no recupera stock y conserva su precio libre."""
    sale_id = db.create_mixed_sale(
        DATE, ROOT_ID,
        unit_lines=[{"item_id": generic_item, "quantity": 2, "price": 150.0}],
        payment_method="Efectivo",
    )
    db.update_sale(
        sale_id,
        items=[{"item_id": generic_item, "quantity": 3, "price": 200.0}],
        vendor_id=ROOT_ID,
        payment_method="Efectivo",
        user_id=ROOT_ID,
    )
    assert db.get_item_stock(generic_item) == 0          # antes se sumaban las 2 viejas
    assert db.get_sale_total(sale_id) == 600.0           # 3 x 200


def test_generico_fuera_de_alertas_de_stock(db, generic_item):
    """Con quantity 0 y mínimo 5, un producto normal alertaría; el genérico no."""
    stats = db.get_dashboard_stats()
    assert all(p["id"] != generic_item for p in stats["low_stock_list"])

    db.check_and_notify_low_stock(ROOT_ID)
    assert db.get_count("SELECT COUNT(*) FROM notifications") == 0
    
def test_update_sale_al_contado_actualiza_lo_cobrado(db, item):
    sale_id = db.create_mixed_sale(
        DATE, ROOT_ID,
        unit_lines=[{"item_id": item, "quantity": 1}],
        payment_method="Efectivo",
    )
    db.update_sale(
        sale_id,
        items=[{"item_id": item, "quantity": 2}],
        vendor_id=ROOT_ID, payment_method="Efectivo", user_id=ROOT_ID,
    )
    assert db.get_single_row("SELECT amount_paid FROM sells WHERE id = ?", (sale_id,))[0] == 160.0

def test_update_sale_al_contado_actualiza_lo_cobrado(db, item):
    sale_id = db.create_mixed_sale(
        DATE, ROOT_ID,
        unit_lines=[{"item_id": item, "quantity": 1}],
        payment_method="Efectivo",
    )
    db.update_sale(
        sale_id,
        items=[{"item_id": item, "quantity": 2}],
        vendor_id=ROOT_ID, payment_method="Efectivo", user_id=ROOT_ID,
    )
    assert db.get_single_row("SELECT amount_paid FROM sells WHERE id = ?", (sale_id,))[0] == 160.0
    
def test_get_sale_by_id_indica_precio_libre(db, item, generic_item):
    sale_id = db.create_mixed_sale(
        DATE, ROOT_ID,
        unit_lines=[
            {"item_id": item, "quantity": 1},
            {"item_id": generic_item, "quantity": 1, "price": 500.0},
        ],
        payment_method="Efectivo",
    )
    sale = db.get_sale_by_id(sale_id)
    flags = {line["item_id"]: line["allow_custom_price"] for line in sale["items"]}
    assert flags == {item: False, generic_item: True}
    
def test_stock_insuficiente_se_captura_como_valueerror(db, item):
    """Un stock insuficiente es una regla de negocio: la API lo trata como 400."""
    with pytest.raises(ValueError):
        db.create_mixed_sale(
            DATE, ROOT_ID,
            unit_lines=[{"item_id": item, "quantity": 999}],
            payment_method="Efectivo",
        )


def test_errores_de_stock_son_a_la_vez_databaseerror():
    from core.bd.bdErrors import DatabaseError, StockError, InsufficientStockError
    err = InsufficientStockError("sin stock")
    assert isinstance(err, StockError) and isinstance(err, DatabaseError) and isinstance(err, ValueError)

def test_update_sale_stock_insuficiente_es_valueerror_y_revierte(db, item):
    sale_id = db.create_mixed_sale(
        DATE, ROOT_ID, unit_lines=[{"item_id": item, "quantity": 2}], payment_method="Efectivo",
    )
    with pytest.raises(InsufficientStockError) as exc:
        db.update_sale(
            sale_id, items=[{"item_id": item, "quantity": 999}],
            vendor_id=ROOT_ID, payment_method="Efectivo", user_id=ROOT_ID,
        )
    assert isinstance(exc.value, ValueError)          # la API lo responde como 400
    assert db.get_item_stock(item) == 8               # la edición fallida no toca nada
    assert db.get_sale_total(sale_id) == 160.0


def test_update_sale_generico_sin_precio_revierte(db, generic_item):
    sale_id = db.create_mixed_sale(
        DATE, ROOT_ID,
        unit_lines=[{"item_id": generic_item, "quantity": 2, "price": 150.0}],
        payment_method="Efectivo",
    )
    with pytest.raises(ValueError):
        db.update_sale(
            sale_id, items=[{"item_id": generic_item, "quantity": 1}],
            vendor_id=ROOT_ID, payment_method="Efectivo", user_id=ROOT_ID,
        )
    assert db.get_sale_total(sale_id) == 300.0


def test_record_bulk_sale_usa_la_misma_regla(db, item, generic_item):
    sale_id = db.record_bulk_sale([{"item_id": item, "quantity": 2}], ROOT_ID)
    assert db.get_item_stock(item) == 8
    assert db.get_sale_total(sale_id) == 160.0
    with pytest.raises(ValueError):                   # genérico sin precio: falla explícito
        db.record_bulk_sale([{"item_id": generic_item, "quantity": 1}], ROOT_ID)
    with pytest.raises(InsufficientStockError):
        db.record_bulk_sale([{"item_id": item, "quantity": 999}], ROOT_ID)
    with pytest.raises(ValueError):
        db.record_bulk_sale([], ROOT_ID)


def test_record_product_sale_delega_y_registra_lo_cobrado(db, item):
    db.record_product_sale(item, 3, ROOT_ID)
    assert db.get_item_stock(item) == 7
    assert db.get_single_row("SELECT amount_paid FROM sells ORDER BY id DESC LIMIT 1")[0] == 240.0
    with pytest.raises(DatabaseError):
        db.record_product_sale(item, 999, ROOT_ID)
    with pytest.raises(DatabaseError):
        db.record_product_sale(99999, 1, ROOT_ID)     # inexistente: antes dejaba una venta suelta
    assert db.get_count("SELECT COUNT(*) FROM sells") == 1
    
"""
AGREGAR AL FINAL de core/bd/tests/mixins/test_sales.py (no es un archivo para ejecutar solo:
usa las fixtures `item`, `weight_item` y `generic_item` y las constantes ROOT_ID / DATE
que ya están definidas en ese archivo).
"""

# ===================== Capa de datos: errores con datos y disponibilidad =====================
from core.bd.bdErrors import ItemNotFoundError, ProductUnavailableError


def test_stock_insuficiente_lleva_los_datos_del_problema(db, item):
    with pytest.raises(InsufficientStockError) as exc:
        db.create_mixed_sale(DATE, ROOT_ID, unit_lines=[{"item_id": item, "quantity": 999}], payment_method="Efectivo")
    assert (exc.value.product, exc.value.requested, exc.value.available) == ("Yerba", 999, 10)


def test_peso_insuficiente_lleva_los_datos_del_problema(db, item, weight_item):
    with pytest.raises(InsufficientStockError) as exc:
        db.create_mixed_sale(
            DATE, ROOT_ID,
            unit_lines=[{"item_id": item, "quantity": 1}],
            weight_lines=[{"weight_item_id": weight_item, "weight": 99999}],
            payment_method="Efectivo",
        )
    assert (exc.value.product, exc.value.requested, exc.value.available) == ("Jamón", 99999, 5000)
    assert db.get_item_stock(item) == 10          # la venta entera se revirtió


def test_producto_inexistente_es_itemnotfound_y_no_deja_ventas(db, item):
    with pytest.raises(ItemNotFoundError) as exc:
        db.create_mixed_sale(DATE, ROOT_ID, unit_lines=[{"item_id": 99999, "quantity": 1}], payment_method="Efectivo")
    assert isinstance(exc.value, ValueError) and isinstance(exc.value, DatabaseError)
    assert db.get_count("SELECT COUNT(*) FROM sells") == 0


def test_producto_por_peso_inexistente(db, item):
    with pytest.raises(ItemNotFoundError):
        db.create_mixed_sale(
            DATE, ROOT_ID,
            unit_lines=[{"item_id": item, "quantity": 1}],
            weight_lines=[{"weight_item_id": 99999, "weight": 100}],
            payment_method="Efectivo",
        )


def test_productos_deshabilitados_se_listan_todos(db, item):
    db.add_item("222", "", "Azúcar", 5, 0, None, 50.0)
    azucar = db.get_single_row("SELECT id FROM items WHERE barrs_code='222'")[0]
    db.disable_item(item)
    db.disable_item(azucar)

    with pytest.raises(ProductUnavailableError) as exc:
        db.create_mixed_sale(
            DATE, ROOT_ID,
            unit_lines=[{"item_id": item, "quantity": 1}, {"item_id": azucar, "quantity": 1}],
            payment_method="Efectivo",
        )
    assert "Yerba" in str(exc.value) and "Azúcar" in str(exc.value)
    assert isinstance(exc.value, ValueError)


def test_las_vias_legacy_tambien_rechazan_productos_deshabilitados(db, item):
    db.disable_item(item)
    with pytest.raises(ProductUnavailableError):
        db.record_bulk_sale([{"item_id": item, "quantity": 1}], ROOT_ID)


def test_editar_una_venta_con_un_producto_deshabilitado_despues_sigue_funcionando(db, item):
    sale_id = db.create_mixed_sale(DATE, ROOT_ID, unit_lines=[{"item_id": item, "quantity": 1}], payment_method="Efectivo")
    db.disable_item(item)

    db.update_sale(
        sale_id, items=[{"item_id": item, "quantity": 2}],
        vendor_id=ROOT_ID, payment_method="Efectivo", user_id=ROOT_ID,
    )
    assert db.get_sale_total(sale_id) == 160.0


def test_create_sale_detailed_devuelve_el_detalle_para_responder(db, item, generic_item, weight_item):
    result = db.create_sale_detailed(
        DATE, ROOT_ID,
        unit_lines=[{"item_id": item, "quantity": 2}, {"item_id": generic_item, "quantity": 1, "price": 500.0}],
        weight_lines=[{"weight_item_id": weight_item, "weight": 250}],
        payment_method="Efectivo",
    )
    assert result["total"] == 700.0                      # 160 + 500 + 40
    assert result["items"] == [
        {"item_id": item, "name": "Yerba", "quantity": 2, "unit_price": 80.0, "subtotal": 160.0},
        {"item_id": generic_item, "name": "Varios", "quantity": 1, "unit_price": 500.0, "subtotal": 500.0},
    ]
    assert result["weight_items"] == [
        {"weight_item_id": weight_item, "name": "Jamón", "weight": 250, "subtotal": 40.0}
    ]
    assert db.get_sale_total(result["sale_id"]) == 700.0
    assert db.create_mixed_sale(
        DATE, ROOT_ID, unit_lines=[{"item_id": item, "quantity": 1}], payment_method="Efectivo"
    ) > result["sale_id"]                                # el atajo sigue devolviendo solo el id


def test_precio_libre_fuera_de_rango(db, generic_item):
    with pytest.raises(ValueError):
        db.create_mixed_sale(
            DATE, ROOT_ID,
            unit_lines=[{"item_id": generic_item, "quantity": 1, "price": 1000001}],
            payment_method="Efectivo",
        )
    assert db.get_count("SELECT COUNT(*) FROM sells") == 0


def test_lo_cobrado_se_guarda_sin_ruido_de_decimales(db, item):
    sale_id = db.create_mixed_sale(DATE, ROOT_ID, unit_lines=[{"item_id": item, "quantity": 3}], payment_method="Efectivo")
    assert db.get_single_row("SELECT amount_paid FROM sells WHERE id = ?", (sale_id,))[0] == 240.0