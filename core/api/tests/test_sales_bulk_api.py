"""
Tests de POST /api/sales/bulk. Describen el comportamiento actual del endpoint:
sirven de red de seguridad antes de simplificar la validación que hoy repite
la API (precio y stock ya los resuelve la capa de datos).
"""
import pytest

URL = "/api/sales/bulk"


def vender(client, items, **extra):
    return client.post(URL, json={"items": items, **extra})


def cantidad_de_ventas(db):
    return db.get_count("SELECT COUNT(*) FROM sells")


# ---------------------------------------------------------------- ventas normales

def test_venta_simple_descuenta_stock_y_devuelve_el_total(client, db, item):
    r = vender(client, [{"item_id": item, "quantity": 2}])

    assert r.status_code == 201
    body = r.get_json()
    assert body["ok"] is True
    assert body["total"] == 160.0
    assert body["items"] == [
        {"item_id": item, "name": "Yerba", "quantity": 2, "unit_price": 80.0, "subtotal": 160.0}
    ]
    assert body["weight_items"] == []
    assert db.get_item_stock(item) == 8
    assert db.get_sale_total(body["sale_id"]) == 160.0


def test_el_precio_enviado_se_ignora_en_productos_normales(client, db, item):
    r = vender(client, [{"item_id": item, "quantity": 1, "price": 1}])

    assert r.status_code == 201
    assert r.get_json()["items"][0]["unit_price"] == 80.0
    assert r.get_json()["total"] == 80.0


def test_stock_insuficiente_devuelve_detalle_y_no_registra_nada(client, db, item):
    r = vender(client, [{"item_id": item, "quantity": 999}])

    assert r.status_code == 400
    assert r.get_json() == {
        "error": "Stock insuficiente", "product": "Yerba", "requested": 999, "available": 10,
    }
    assert db.get_item_stock(item) == 10
    assert cantidad_de_ventas(db) == 0


def test_un_producto_sin_stock_no_deja_vender_ninguna_linea(client, db, item):
    """Si una línea falla, la venta entera se rechaza: el stock del resto no se toca."""
    db.add_item("222", "", "Azúcar", 1, 0, None, 50.0)
    azucar = db.get_single_row("SELECT id FROM items WHERE barrs_code='222'")[0]

    r = vender(client, [{"item_id": item, "quantity": 2}, {"item_id": azucar, "quantity": 5}])

    assert r.status_code == 400
    assert db.get_item_stock(item) == 10
    assert db.get_item_stock(azucar) == 1
    assert cantidad_de_ventas(db) == 0


# ---------------------------------------------------------------- validaciones de formato

@pytest.mark.parametrize("cantidad", [0, -1, "abc", None])
def test_cantidades_invalidas_se_rechazan(client, db, item, cantidad):
    r = vender(client, [{"item_id": item, "quantity": cantidad}])

    assert r.status_code == 400
    assert "error" in r.get_json()
    assert db.get_item_stock(item) == 10
    assert cantidad_de_ventas(db) == 0


def test_item_id_invalido_se_rechaza(client):
    r = vender(client, [{"item_id": "xyz", "quantity": 1}])
    assert r.status_code == 400


@pytest.mark.parametrize("cuerpo", [{}, {"items": []}, {"items": [], "weight_items": []}])
def test_sin_productos_se_rechaza(client, cuerpo):
    r = client.post(URL, json=cuerpo)

    assert r.status_code == 400
    assert r.get_json()["error"] == "La venta necesita al menos un producto"


def test_items_que_no_son_lista_se_rechazan(client):
    r = client.post(URL, json={"items": "no-es-una-lista"})

    assert r.status_code == 400
    assert r.get_json()["error"].startswith("Formato inválido")


def test_un_json_roto_se_trata_como_venta_vacia(client):
    r = client.post(URL, data='{"items": [', content_type="application/json")

    assert r.status_code == 400
    assert "error" in r.get_json()


def test_producto_inexistente(client):
    r = vender(client, [{"item_id": 99999, "quantity": 1}])

    assert r.status_code == 400
    assert r.get_json()["error"] == "Producto con ID 99999 no encontrado"


def test_producto_deshabilitado(client, db, item):
    db.disable_item(item)

    r = vender(client, [{"item_id": item, "quantity": 1}])

    assert r.status_code == 400
    assert "no están disponibles" in r.get_json()["error"]
    assert "Yerba" in r.get_json()["error"]
    assert db.get_item_stock(item) == 10


# ---------------------------------------------------------------- producto en blanco

def test_generico_se_vende_con_precio_libre_y_sin_stock(client, db, generic_item):
    r = vender(client, [{"item_id": generic_item, "quantity": 3, "price": 150}])

    assert r.status_code == 201
    body = r.get_json()
    assert body["total"] == 450.0
    assert body["items"][0]["unit_price"] == 150.0
    assert db.get_item_stock(generic_item) == 0


@pytest.mark.parametrize("precio", [None, 0, -5, 1000001])
def test_generico_exige_un_precio_valido(client, db, generic_item, precio):
    linea = {"item_id": generic_item, "quantity": 1}
    if precio is not None:
        linea["price"] = precio

    r = vender(client, [linea])

    assert r.status_code == 400
    assert "requiere un precio" in r.get_json()["error"]
    assert cantidad_de_ventas(db) == 0


def test_venta_con_producto_normal_y_generico(client, db, item, generic_item):
    r = vender(client, [
        {"item_id": item, "quantity": 2},
        {"item_id": generic_item, "quantity": 1, "price": 500},
    ])

    assert r.status_code == 201
    assert r.get_json()["total"] == 660.0
    assert db.get_item_stock(item) == 8
    assert db.get_item_stock(generic_item) == 0


# ---------------------------------------------------------------- pago y crédito

def test_metodo_de_pago_invalido(client, item):
    r = vender(client, [{"item_id": item, "quantity": 1}], payment_method="Cripto")

    assert r.status_code == 400
    assert r.get_json()["error"] == "payment_method inválido: Cripto"


def test_fiado_requiere_cliente(client, db, item):
    r = vender(client, [{"item_id": item, "quantity": 1}], payment_method="Fiado")

    assert r.status_code == 400
    assert r.get_json()["error"] == "Debe seleccionar un cliente para venta fiada"
    assert cantidad_de_ventas(db) == 0


def test_fiado_genera_deuda_por_el_total(client, db, item):
    cliente = db.create_customer("Ana", None, 1000)

    r = vender(client, [{"item_id": item, "quantity": 2}], payment_method="Fiado", customer_id=cliente)

    assert r.status_code == 201
    assert db.get_customer_balance(cliente) == 160.0


def test_mixto_fia_solo_la_diferencia(client, db, item):
    cliente = db.create_customer("Ana", None, 1000)

    r = vender(client, [{"item_id": item, "quantity": 2}],
               payment_method="Mixto", customer_id=cliente, amount_paid=60)

    assert r.status_code == 201
    assert db.get_customer_balance(cliente) == 100.0


def test_mixto_con_monto_igual_al_total_se_rechaza(client, db, item):
    cliente = db.create_customer("Ana", None, 1000)

    r = vender(client, [{"item_id": item, "quantity": 2}],
               payment_method="Mixto", customer_id=cliente, amount_paid=160)

    assert r.status_code == 400
    assert r.get_json()["ok"] is False
    assert db.get_item_stock(item) == 10
    assert cantidad_de_ventas(db) == 0


def test_limite_de_credito_superado_revierte_la_venta(client, db, item):
    cliente = db.create_customer("Ana", None, 100)

    r = vender(client, [{"item_id": item, "quantity": 2}], payment_method="Fiado", customer_id=cliente)

    assert r.status_code == 400
    body = r.get_json()
    assert body["code"] == "credit_limit_exceeded"
    assert body["ok"] is False
    assert db.get_item_stock(item) == 10
    assert cantidad_de_ventas(db) == 0


def test_force_credit_permite_superar_el_limite_siendo_root(client, db, item):
    cliente = db.create_customer("Ana", None, 100)

    r = vender(client, [{"item_id": item, "quantity": 2}],
               payment_method="Fiado", customer_id=cliente, force_credit=True)

    assert r.status_code == 201
    assert db.get_customer_balance(cliente) == 160.0


def test_force_credit_sin_permisos_se_rechaza(vendor_client, db, item):
    cliente = db.create_customer("Ana", None, 100)

    r = vender(vendor_client, [{"item_id": item, "quantity": 2}],
               payment_method="Fiado", customer_id=cliente, force_credit=True)

    assert r.status_code == 403
    assert r.get_json()["error"] == "Solo un admin puede forzar el límite de crédito"
    assert cantidad_de_ventas(db) == 0


# ---------------------------------------------------------------- acceso

def test_un_vendedor_puede_registrar_ventas(vendor_client, db, item):
    r = vender(vendor_client, [{"item_id": item, "quantity": 1}])

    assert r.status_code == 201
    assert db.get_item_stock(item) == 9


def test_sin_sesion_devuelve_401(anon_client, db, item):
    r = vender(anon_client, [{"item_id": item, "quantity": 1}])

    assert r.status_code == 401
    assert r.get_json() == {"error": "No autenticado"}
    assert db.get_item_stock(item) == 10


# ---------------------------------------------------------------- productos por peso

@pytest.fixture
def jamon(db):
    """Producto por peso: $80 cada 500 g, con 5000 g en stock. Devuelve su id."""
    return db.add_weight_item("Jamón", 5000, 80.0, 500)


def peso_en_stock(db, weight_item_id):
    return db.get_single_row("SELECT weight FROM weight_items WHERE id = ?", (weight_item_id,))[0]


def test_venta_con_producto_por_unidad_y_por_peso(client, db, item, jamon):
    r = client.post(URL, json={
        "items": [{"item_id": item, "quantity": 1}],
        "weight_items": [{"weight_item_id": jamon, "weight": 250}],
    })

    assert r.status_code == 201
    body = r.get_json()
    assert body["weight_items"] == [{"weight_item_id": jamon, "name": "Jamón", "weight": 250.0, "subtotal": 40.0}]
    assert body["total"] == 120.0                       # 80 + 40
    assert peso_en_stock(db, jamon) == 4750
    assert db.get_item_stock(item) == 9


def test_peso_insuficiente_devuelve_detalle_y_no_registra_nada(client, db, item, jamon):
    r = client.post(URL, json={
        "items": [{"item_id": item, "quantity": 1}],
        "weight_items": [{"weight_item_id": jamon, "weight": 99999}],
    })

    assert r.status_code == 400
    assert r.get_json() == {"error": "Stock insuficiente", "product": "Jamón", "requested": 99999.0, "available": 5000}
    assert peso_en_stock(db, jamon) == 5000
    assert db.get_item_stock(item) == 10
    assert cantidad_de_ventas(db) == 0


@pytest.mark.parametrize("peso", [0, -50, "abc"])
def test_pesos_invalidos_se_rechazan(client, db, item, jamon, peso):
    r = client.post(URL, json={
        "items": [{"item_id": item, "quantity": 1}],
        "weight_items": [{"weight_item_id": jamon, "weight": peso}],
    })

    assert r.status_code == 400
    assert cantidad_de_ventas(db) == 0


def test_producto_por_peso_inexistente(client, item):
    r = client.post(URL, json={
        "items": [{"item_id": item, "quantity": 1}],
        "weight_items": [{"weight_item_id": 99999, "weight": 100}],
    })

    assert r.status_code == 400
    assert r.get_json()["error"] == "Producto (por peso) con ID 99999 no encontrado"


def test_producto_por_peso_deshabilitado(client, db, item, jamon):
    db.execute_query("UPDATE weight_items SET status = 0 WHERE id = ?", (jamon,), fetch=False)

    r = client.post(URL, json={
        "items": [{"item_id": item, "quantity": 1}],
        "weight_items": [{"weight_item_id": jamon, "weight": 100}],
    })

    assert r.status_code == 400
    assert "no están disponibles" in r.get_json()["error"]
    assert "Jamón" in r.get_json()["error"]


def test_se_listan_todos_los_productos_deshabilitados(client, db, item, jamon):
    db.disable_item(item)
    db.execute_query("UPDATE weight_items SET status = 0 WHERE id = ?", (jamon,), fetch=False)

    r = client.post(URL, json={
        "items": [{"item_id": item, "quantity": 1}],
        "weight_items": [{"weight_item_id": jamon, "weight": 100}],
    })

    assert r.status_code == 400
    assert "Yerba" in r.get_json()["error"] and "Jamón" in r.get_json()["error"]


@pytest.mark.xfail(strict=True, reason="Limitación conocida: 'sells.item_id' es NOT NULL, una venta solo por peso devuelve 500")
def test_venta_solo_por_peso_deberia_poder_registrarse(client, jamon):
    r = client.post(URL, json={"weight_items": [{"weight_item_id": jamon, "weight": 250}]})

    assert r.status_code == 201