"""
Tests de GET /api/sales/<id>/edit y PUT /api/sales/<id>.
"""
import pytest

BULK = "/api/sales/bulk"


def crear_venta(client, items, **extra):
    r = client.post(BULK, json={"items": items, **extra})
    assert r.status_code == 201, r.get_json()
    return r.get_json()["sale_id"]


def editar(client, sale_id, items, **extra):
    cuerpo = {"vendor_id": 1, "payment_method": "Efectivo", "items": items}
    cuerpo.update(extra)
    return client.put(f"/api/sales/{sale_id}", json=cuerpo)


# ---------------------------------------------------------------- lectura para editar

def test_get_para_editar_devuelve_lineas_y_marca_las_de_precio_libre(client, db, item, generic_item):
    sale_id = crear_venta(client, [
        {"item_id": item, "quantity": 1},
        {"item_id": generic_item, "quantity": 2, "price": 150},
    ])

    r = client.get(f"/api/sales/{sale_id}/edit")

    assert r.status_code == 200
    body = r.get_json()
    assert body["id"] == sale_id
    assert body["payment_method"] == "Efectivo"
    flags = {line["item_id"]: line["allow_custom_price"] for line in body["items"]}
    assert flags == {item: False, generic_item: True}
    precios = {line["item_id"]: line["price"] for line in body["items"]}
    assert precios == {item: 80.0, generic_item: 150.0}


def test_get_para_editar_venta_inexistente(client):
    r = client.get("/api/sales/99999/edit")

    assert r.status_code == 404
    assert r.get_json()["error"] == "Venta no encontrada"


# ---------------------------------------------------------------- edición

def test_editar_ajusta_stock_y_total(client, db, item):
    sale_id = crear_venta(client, [{"item_id": item, "quantity": 2}])
    assert db.get_item_stock(item) == 8

    r = editar(client, sale_id, [{"item_id": item, "quantity": 5}])

    assert r.status_code == 200
    assert r.get_json()["message"] == "Venta actualizada exitosamente"
    assert db.get_item_stock(item) == 5
    assert db.get_sale_total(sale_id) == 400.0


def test_editar_una_venta_al_contado_actualiza_lo_cobrado(client, db, item):
    sale_id = crear_venta(client, [{"item_id": item, "quantity": 1}])

    editar(client, sale_id, [{"item_id": item, "quantity": 3}])

    assert db.get_single_row("SELECT amount_paid FROM sells WHERE id = ?", (sale_id,))[0] == 240.0


def test_editar_con_stock_insuficiente_no_cambia_nada(client, db, item):
    sale_id = crear_venta(client, [{"item_id": item, "quantity": 2}])

    r = editar(client, sale_id, [{"item_id": item, "quantity": 999}])

    assert r.status_code == 400
    assert "Stock insuficiente" in r.get_json()["error"]
    assert db.get_item_stock(item) == 8
    assert db.get_sale_total(sale_id) == 160.0


def test_editar_cambia_el_precio_de_un_producto_de_precio_libre(client, db, generic_item):
    sale_id = crear_venta(client, [{"item_id": generic_item, "quantity": 2, "price": 150}])

    r = editar(client, sale_id, [{"item_id": generic_item, "quantity": 3, "price": 200}])

    assert r.status_code == 200
    assert db.get_item_stock(generic_item) == 0
    assert db.get_sale_total(sale_id) == 600.0


def test_editar_un_producto_de_precio_libre_sin_precio_se_rechaza(client, db, generic_item):
    sale_id = crear_venta(client, [{"item_id": generic_item, "quantity": 2, "price": 150}])

    r = editar(client, sale_id, [{"item_id": generic_item, "quantity": 1}])

    assert r.status_code == 400
    assert "requiere un precio" in r.get_json()["error"]
    assert db.get_sale_total(sale_id) == 300.0


def test_editar_ignora_el_precio_enviado_en_productos_normales(client, db, item):
    sale_id = crear_venta(client, [{"item_id": item, "quantity": 1}])

    editar(client, sale_id, [{"item_id": item, "quantity": 2, "price": 1}])

    assert db.get_sale_total(sale_id) == 160.0


# ---------------------------------------------------------------- validaciones

def test_editar_con_json_roto(client, db, item):
    sale_id = crear_venta(client, [{"item_id": item, "quantity": 1}])

    r = client.put(f"/api/sales/{sale_id}", data='{"items": [', content_type="application/json")

    assert r.status_code == 400
    assert r.get_json()["error"] == "JSON inválido"


def test_editar_con_items_que_no_son_lista(client, db, item):
    sale_id = crear_venta(client, [{"item_id": item, "quantity": 1}])

    r = client.put(f"/api/sales/{sale_id}", json={"vendor_id": 1, "payment_method": "Efectivo", "items": "x"})

    assert r.status_code == 400
    assert r.get_json()["error"] == "Items inválidos"


def test_editar_sin_vendedor_o_metodo_de_pago(client, db, item):
    sale_id = crear_venta(client, [{"item_id": item, "quantity": 1}])

    r = client.put(f"/api/sales/{sale_id}", json={"items": [{"item_id": item, "quantity": 1}]})

    assert r.status_code == 400
    assert r.get_json()["error"] == "Faltan campos requeridos"


@pytest.mark.parametrize("cantidad", [0, -2, "abc"])
def test_editar_con_cantidades_invalidas(client, db, item, cantidad):
    sale_id = crear_venta(client, [{"item_id": item, "quantity": 2}])

    r = editar(client, sale_id, [{"item_id": item, "quantity": cantidad}])

    assert r.status_code == 400
    assert db.get_item_stock(item) == 8
    assert db.get_sale_total(sale_id) == 160.0


def test_editar_sin_sesion_devuelve_401(anon_client, db, item):
    r = editar(anon_client, 1, [{"item_id": item, "quantity": 1}])

    assert r.status_code == 401


@pytest.mark.xfail(strict=True, reason="Hoy devuelve 500 'Error interno'; una venta inexistente debería dar 404")
def test_editar_una_venta_inexistente_deberia_dar_404(client, item):
    r = editar(client, 99999, [{"item_id": item, "quantity": 1}])

    assert r.status_code == 404
