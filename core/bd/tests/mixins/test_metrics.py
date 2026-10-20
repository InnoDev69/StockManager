import pytest

ROOT_ID = 1


@pytest.fixture
def item_id(db):
    db.add_item("777", "", "Café", 20, 5, None, 100.0)
    return db.get_single_row("SELECT id FROM items WHERE barrs_code='777'")[0]


def test_metrics_en_base_vacia(db):
    data = db.get_metrics_data("2026-10-01", "2026-10-31", "2026-09-01", "2026-09-30")
    assert data["kpis"] == (0, 0, 0, 0, 0, 0)
    assert data["debtors"] == {"items": [], "count": 0, "totalDebt": 0.0}
    assert db.get_vendors_metrics("2026-10-01", "2026-10-31", "2026-09-01", "2026-09-30") == []


def test_metrics_ingresos_cobrados_y_deudores(db, item_id):
    cliente = db.create_customer("Carlos")

    # Venta 1 (Contado): 2 unidades x $100 = $200 cobrados
    db.create_mixed_sale(
        "2026-10-10", ROOT_ID,
        unit_lines=[{"item_id": item_id, "quantity": 2}],
        payment_method="Efectivo",
    )
    # Venta 2 (Mixto): 1 unidad x $100, paga $40 y fía $60
    db.create_mixed_sale(
        "2026-10-12", ROOT_ID,
        unit_lines=[{"item_id": item_id, "quantity": 1}],
        payment_method="Mixto",
        customer_id=cliente,
        amount_paid=40.0,
    )

    data = db.get_metrics_data("2026-10-01", "2026-10-31", "2026-09-01", "2026-09-30")
    total_collected, sales_count, units_sold, gross_amount, sales_collected, payments_collected = data["kpis"]

    assert sales_count == 2
    assert units_sold == 3
    assert gross_amount == 300.0       # 200 + 100 facturados
    assert sales_collected == 240.0    # 200 + 40 cobrados en el momento
    assert payments_collected == 0.0
    assert total_collected == 240.0

    # Snapshot de deudores debe reflejar los $60 pendientes de Carlos
    assert data["debtors"]["count"] == 1
    assert data["debtors"]["totalDebt"] == 60.0


def test_vendors_metrics_comparacion_entre_periodos(db, item_id):
    # Periodo anterior (Septiembre): 1 venta de $100
    db.create_mixed_sale(
        "2026-09-15", ROOT_ID,
        unit_lines=[{"item_id": item_id, "quantity": 1}],
        payment_method="Efectivo",
    )
    # Periodo actual (Octubre): 2 ventas por un total de $300
    db.create_mixed_sale(
        "2026-10-10", ROOT_ID,
        unit_lines=[{"item_id": item_id, "quantity": 1}],
        payment_method="Efectivo",
    )
    db.create_mixed_sale(
        "2026-10-15", ROOT_ID,
        unit_lines=[{"item_id": item_id, "quantity": 2}],
        payment_method="Efectivo",
    )

    vendors = db.get_vendors_metrics("2026-10-01", "2026-10-31", "2026-09-01", "2026-09-30")
    assert len(vendors) == 1
    v = vendors[0]
    assert v["name"] == "root"
    assert v["revenue"] == 300.0
    assert v["salesCount"] == 2
    assert v["unitsSold"] == 3
    assert v["avgTicket"] == 150.0
    assert v["revenueChange"] == 200.0  # de $100 a $300 = +200%
    assert v["salesChange"] == 100.0    # de 1 a 2 ventas = +100%