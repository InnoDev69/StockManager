import csv
import pytest
from core.bd.bdErrors import DatabaseError

ROOT_ID = 1


@pytest.fixture
def item_id(db):
    """Producto activo con stock 10 y mínimo 5."""
    db.add_item("7791234567890", "Paquete 1kg", "Yerba Mate", 10, 5, "2027-01-01", 1500.0)
    return db.get_single_row("SELECT id FROM items WHERE barrs_code='7791234567890'")[0]


# ---------- Alta y lecturas básicas ----------

def test_add_item_y_getters_basicos(db, item_id):
    assert db.get_item_name(item_id) == "Yerba Mate"
    assert db.get_item_stock(item_id) == 10

    info = db.get_item_by_id(item_id)
    assert info["barrs_code"] == "7791234567890"
    assert info["stock"] == 10
    assert info["min_stock"] == 5
    assert info["price"] == 1500.0
    assert info["status"] == 1


def test_getters_producto_inexistente(db):
    assert db.get_item_by_id(9999) is None
    assert db.get_item_details(9999) is None
    assert db.get_item_name(9999) is None
    assert db.get_item_stock(9999) is None


def test_add_item_codigo_duplicado_falla(db, item_id):
    with pytest.raises(DatabaseError):
        db.add_item("7791234567890", "", "Otro Producto", 5, 1, None, 100.0)


def test_add_item_sin_codigo_permite_multiples(db):
    """barrs_code vacío se guarda como NULL y SQLite permite múltiples NULL en UNIQUE."""
    db.add_item("", "", "Suelto 1", 10, 2, None, 50.0)
    db.add_item("   ", "", "Suelto 2", 10, 2, None, 60.0)
    assert db.get_count("SELECT COUNT(*) FROM items WHERE barrs_code IS NULL") == 2


# ---------- Estado (enable / disable / activate) ----------

def test_disable_enable_y_activate_item(db, item_id):
    db.disable_item(item_id)
    assert db.get_item_by_id(item_id)["status"] == 0
    assert db.get_all_items() == []  # get_all_items solo trae activos (status=1)

    db.enable_item(item_id)
    assert db.get_item_by_id(item_id)["status"] == 1
    assert len(db.get_all_items()) == 1

    db.disable_item(item_id)
    db.activate_item(item_id)
    assert db.get_item_by_id(item_id)["status"] == 1


# ---------- Código de barras ----------

def test_update_item_barcode(db, item_id):
    db.update_item_barcode(item_id, "999888")
    assert db.get_item_by_id(item_id)["barrs_code"] == "999888"


def test_update_item_barcode_colision_falla(db, item_id):
    db.add_item("555555", "", "Azúcar", 10, 2, None, 800.0)
    with pytest.raises(DatabaseError):
        db.update_item_barcode(item_id, "555555")


@pytest.mark.parametrize("codigo,esperado", [
    ("7791234567890", "ean13"),
    ("12345678", "ean8"),
    ("123456789012", "upca"),
    ("123456", "upce"),
    ("978-3-16-148410-0", "isbn13"),
    ("012345678X", "isbn10"),
    ("PRD000123", "code128"),
    ("ABC-123", "code128"),
    ("", "code128"),
])
def test_detect_barcode_type(db, codigo, esperado):
    assert db._detect_barcode_type(codigo) == esperado


# ---------- Alertas de stock bajo ----------

def test_check_and_notify_low_stock_ciclo_completo(db):
    """Notifica una sola vez cuando quantity < min_quantity y resetea al reponer."""
    db.add_item("101", "", "Leche", 2, 5, None, 1000.0)  # 2 < 5 -> bajo stock
    item_id = db.get_single_row("SELECT id FROM items WHERE barrs_code='101'")[0]

    # 1ra pasada: crea notificación y marca notified_low_stock = 1
    db.check_and_notify_low_stock(ROOT_ID)
    assert db.get_unread_count(ROOT_ID) == 1
    assert db.get_single_row("SELECT notified_low_stock FROM items WHERE id=?", (item_id,))[0] == 1

    # 2da pasada sin cambios: no duplica la notificación
    db.check_and_notify_low_stock(ROOT_ID)
    assert db.get_unread_count(ROOT_ID) == 1

    # Reposición de stock (>= min_quantity): resetea el flag notified_low_stock a 0
    db.execute_query("UPDATE items SET quantity = 10 WHERE id = ?", (item_id,), fetch=False)
    db.check_and_notify_low_stock(ROOT_ID)
    assert db.get_single_row("SELECT notified_low_stock FROM items WHERE id=?", (item_id,))[0] == 0


# ---------- Exportación CSV ----------

def test_export_csv_sin_filtros_y_con_filtros(db, tmp_path):
    db.add_item("001", "Desc A", "Arroz", 10, 2, None, 500.0)
    db.add_item("002", "Desc B", "Fideos", 0, 2, None, 300.0)

    # 1. Sin filtros (usa get_all_items) y excluyendo columnas con 'filter'
    csv_all = tmp_path / "all.csv"
    db.export_csv(str(csv_all), filter=["description", "expiration_date"])
    with open(csv_all, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    assert "description" not in rows[0]
    assert [r["name"] for r in rows] == ["Arroz", "Fideos"]

    # 2. Con filtro view_mode="out_of_stock"
    csv_out = tmp_path / "out.csv"
    db.export_csv(str(csv_out), view_mode="out_of_stock")
    with open(csv_out, encoding="utf-8") as f:
        rows_out = list(csv.DictReader(f))
    assert len(rows_out) == 1
    assert rows_out[0]["name"] == "Fideos"

    # 3. Con búsqueda y orden descendente por precio
    csv_sort = tmp_path / "sort.csv"
    db.export_csv(str(csv_sort), sort="price", order="desc")
    with open(csv_sort, encoding="utf-8") as f:
        rows_sort = list(csv.DictReader(f))
    assert [r["name"] for r in rows_sort] == ["Arroz", "Fideos"]