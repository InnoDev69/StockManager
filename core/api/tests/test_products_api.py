"""
Tests de la API de productos (core/api/products_api.py):
alta, lectura, edición, baja/alta lógica, búsqueda y actualizaciones masivas.
"""
import pytest

PRODUCTS = "/api/products"


def nuevo(**extra):
    cuerpo = {"barcode": "555", "name": "Fideos", "description": "Tallarín",
              "quantity": 20, "min_quantity": 5, "price": 120.0}
    cuerpo.update(extra)
    return cuerpo


def crear(client, **extra):
    r = client.post(PRODUCTS, json=nuevo(**extra))
    assert r.status_code == 201, r.get_json()


@pytest.fixture
def sin_permisos(monkeypatch):
    """Ningún rol (salvo root, que siempre pasa) tiene permisos: no depende de la config de roles."""
    monkeypatch.setattr("core.services.permissions_service.has_permission", lambda *a, **k: False)


def id_por_codigo(db, codigo):
    return db.get_single_row("SELECT id FROM items WHERE barrs_code = ?", (codigo,))[0]


# ---------------------------------------------------------------- crear

def test_crear_producto_normal(client, db):
    r = client.post(PRODUCTS, json=nuevo())

    assert r.status_code == 201
    assert r.get_json()["message"] == "Producto creado exitosamente"
    pid = id_por_codigo(db, "555")
    p = client.get(f"{PRODUCTS}/{pid}").get_json()
    assert p["name"] == "Fideos"
    assert p["stock"] == 20
    assert p["min_stock"] == 5
    assert p["price"] == 120.0
    assert p["track_stock"] is True
    assert p["allow_custom_price"] is False


def test_crear_producto_en_blanco_no_pide_cantidades_ni_precio(client, db):
    r = client.post(PRODUCTS, json={"barcode": "GEN", "name": "Varios",
                                    "track_stock": False, "allow_custom_price": True})

    assert r.status_code == 201
    p = client.get(f"{PRODUCTS}/{id_por_codigo(db, 'GEN')}").get_json()
    assert p["track_stock"] is False
    assert p["allow_custom_price"] is True
    assert p["stock"] == 0
    assert p["price"] == 0


@pytest.mark.parametrize("valor", ["true", "false", "1", "0", 1, 0, True, False])
def test_los_flags_aceptan_distintas_formas(client, valor):
    r = client.post(PRODUCTS, json=nuevo(track_stock=valor, quantity=1, min_quantity=0))

    assert r.status_code == 201


@pytest.mark.parametrize("campo", ["track_stock", "allow_custom_price"])
@pytest.mark.parametrize("valor", ["quizas", 2, 1.5, []])
def test_los_flags_invalidos_se_rechazan(client, db, campo, valor):
    r = client.post(PRODUCTS, json=nuevo(**{campo: valor}))

    assert r.status_code == 400
    assert "inválido" in r.get_json()["error"]
    assert db.get_count("SELECT COUNT(*) FROM items") == 0


@pytest.mark.parametrize("faltante", ["barcode", "name", "quantity", "min_quantity", "price"])
def test_crear_sin_campos_requeridos(client, db, faltante):
    cuerpo = nuevo()
    del cuerpo[faltante]

    r = client.post(PRODUCTS, json=cuerpo)

    assert r.status_code == 400
    assert r.get_json()["error"] == "Faltan campos requeridos"
    assert db.get_count("SELECT COUNT(*) FROM items") == 0


def test_crear_con_codigo_de_barras_repetido(client, db):
    crear(client)

    r = client.post(PRODUCTS, json=nuevo())

    assert r.status_code == 409
    assert db.get_count("SELECT COUNT(*) FROM items") == 1


def test_crear_sin_permiso_devuelve_403(vendor_client, db, sin_permisos):
    r = vendor_client.post(PRODUCTS, json=nuevo())

    assert r.status_code == 403
    assert db.get_count("SELECT COUNT(*) FROM items") == 0


def test_crear_sin_sesion_devuelve_401(anon_client):
    assert anon_client.post(PRODUCTS, json=nuevo()).status_code == 401


# ---------------------------------------------------------------- leer

def test_leer_un_producto(client, item):
    r = client.get(f"{PRODUCTS}/{item}")

    assert r.status_code == 200
    body = r.get_json()
    assert body["id"] == item
    assert body["barcode"] == "111"
    assert body["name"] == "Yerba"
    assert body["price"] == 80.0


def test_leer_un_producto_inexistente(client):
    r = client.get(f"{PRODUCTS}/99999")

    assert r.status_code == 404
    assert r.get_json()["error"] == "Producto no encontrado"


def test_un_vendedor_puede_leer_productos(vendor_client, item):
    assert vendor_client.get(f"{PRODUCTS}/{item}").status_code == 200


def test_leer_sin_sesion_devuelve_401(anon_client, item):
    assert anon_client.get(f"{PRODUCTS}/{item}").status_code == 401


# ---------------------------------------------------------------- editar

def test_editar_precio_y_nombre(client, db, item):
    r = client.put(f"{PRODUCTS}/{item}", json={"name": "Yerba Premium", "price": 95.5})

    assert r.status_code == 200
    assert r.get_json()["message"] == "Producto actualizado"
    p = client.get(f"{PRODUCTS}/{item}").get_json()
    assert (p["name"], p["price"]) == ("Yerba Premium", 95.5)


def test_editar_no_toca_los_campos_no_enviados(client, item):
    client.put(f"{PRODUCTS}/{item}", json={"price": 99})

    p = client.get(f"{PRODUCTS}/{item}").get_json()
    assert p["name"] == "Yerba"
    assert p["stock"] == 10


def test_editar_sin_cambios_reales_devuelve_400(client, item):
    r = client.put(f"{PRODUCTS}/{item}", json={"name": "Yerba", "price": 80.0})

    assert r.status_code == 400
    assert r.get_json()["error"] == "No hay datos para actualizar"


@pytest.mark.parametrize("cuerpo", [{}, {"campo_desconocido": 1}])
def test_editar_sin_datos_utiles_devuelve_400(client, item, cuerpo):
    r = client.put(f"{PRODUCTS}/{item}", json=cuerpo)

    assert r.status_code == 400


def test_editar_actualiza_updated_at(client, db, item):
    db.execute_query("UPDATE items SET updated_at = ? WHERE id = ?", ("2000-01-01", item), fetch=False)

    client.put(f"{PRODUCTS}/{item}", json={"price": 1000})

    assert client.get(f"{PRODUCTS}/{item}").get_json()["updated_at"] != "2000-01-01"


def test_editar_sin_cambios_no_toca_updated_at(client, db, item):
    db.execute_query("UPDATE items SET updated_at = ? WHERE id = ?", ("2000-01-01", item), fetch=False)

    client.put(f"{PRODUCTS}/{item}", json={"price": 80.0})

    assert client.get(f"{PRODUCTS}/{item}").get_json()["updated_at"] == "2000-01-01"


def test_editar_flag_invalido(client, item):
    r = client.put(f"{PRODUCTS}/{item}", json={"track_stock": "quizas"})

    assert r.status_code == 400
    assert "track_stock inválido" in r.get_json()["error"]


def test_editar_el_flag_de_precio_libre(client, item):
    r = client.put(f"{PRODUCTS}/{item}", json={"allow_custom_price": "true"})

    assert r.status_code == 200
    assert client.get(f"{PRODUCTS}/{item}").get_json()["allow_custom_price"] is True


def test_editar_sin_permiso_devuelve_403(vendor_client, client, item, sin_permisos):
    r = vendor_client.put(f"{PRODUCTS}/{item}", json={"price": 1})

    assert r.status_code == 403
    assert client.get(f"{PRODUCTS}/{item}").get_json()["price"] == 80.0


def test_editar_sin_sesion_devuelve_401(anon_client, item):
    assert anon_client.put(f"{PRODUCTS}/{item}", json={"price": 1}).status_code == 401


def test_editar_un_producto_inexistente_devuelve_404(client):
    r = client.put(f"{PRODUCTS}/99999", json={"price": 1})

    assert r.status_code == 404
    assert r.get_json()["error"] == "Producto no encontrado"


# ---------------------------------------------------------------- deshabilitar / activar

def test_deshabilitar_un_producto_lo_saca_de_la_busqueda(client, db, item):
    r = client.delete(f"{PRODUCTS}/{item}")

    assert r.status_code == 200
    assert r.get_json()["message"] == "Producto deshabilitado"
    assert client.get("/api/items", query_string={"q": "Yerba"}).get_json() == []


def test_deshabilitar_no_borra_el_registro(client, db, item):
    client.delete(f"{PRODUCTS}/{item}")

    assert db.get_count("SELECT COUNT(*) FROM items") == 1
    assert db.get_single_row("SELECT status FROM items WHERE id = ?", (item,))[0] == 0


def test_activar_un_producto_deshabilitado(client, db, item):
    db.disable_item(item)

    r = client.post(f"{PRODUCTS}/{item}/activate")

    assert r.status_code == 200
    assert r.get_json()["message"] == "Producto activado"
    assert len(client.get("/api/items", query_string={"q": "Yerba"}).get_json()) == 1


#@pytest.mark.xfail(strict=False, reason="Pendiente: delete/activate no chequean que el producto exista")
def test_deshabilitar_un_producto_inexistente_devuelve_404(client, db):
    r = client.delete(f"{PRODUCTS}/99999")

    assert r.status_code == 404
    assert db.get_count("SELECT COUNT(*) FROM notifications") == 0


#@pytest.mark.xfail(strict=False, reason="Pendiente: delete/activate no chequean que el producto exista")
def test_activar_un_producto_inexistente_devuelve_404(client):
    r = client.post(f"{PRODUCTS}/99999/activate")

    assert r.status_code == 404


def test_deshabilitar_y_activar_sin_permiso_devuelve_403(vendor_client, item, sin_permisos):
    assert vendor_client.delete(f"{PRODUCTS}/{item}").status_code == 403
    assert vendor_client.post(f"{PRODUCTS}/{item}/activate").status_code == 403


def test_deshabilitar_sin_sesion_devuelve_401(anon_client, item):
    assert anon_client.delete(f"{PRODUCTS}/{item}").status_code == 401


# ---------------------------------------------------------------- búsqueda

def test_busqueda_vacia_devuelve_lista_vacia(client, item):
    for q in ("", "   "):
        r = client.get("/api/items", query_string={"q": q})
        assert r.status_code == 200
        assert r.get_json() == []

    assert client.get("/api/items").get_json() == []


def test_busqueda_por_nombre_parcial_sin_importar_mayusculas(client, item):
    r = client.get("/api/items", query_string={"q": "yer"})

    assert [p["name"] for p in r.get_json()] == ["Yerba"]


def test_busqueda_por_codigo_de_barras(client, item):
    r = client.get("/api/items", query_string={"q": "111"})

    body = r.get_json()
    assert len(body) == 1
    assert body[0]["id"] == item
    assert body[0]["track_stock"] is True
    assert body[0]["allow_custom_price"] is False


def test_busqueda_sin_coincidencias(client, item):
    assert client.get("/api/items", query_string={"q": "zzzz"}).get_json() == []


def test_busqueda_devuelve_como_maximo_10(client, db):
    for i in range(15):
        db.add_item(f"COD{i:02d}", "", f"Galletita {i}", 1, 0, None, 10.0)

    r = client.get("/api/items", query_string={"q": "Galletita"})

    assert len(r.get_json()) == 10


def test_busqueda_marca_el_producto_generico(client, generic_item):
    p = client.get("/api/items", query_string={"q": "Varios"}).get_json()[0]

    assert p["track_stock"] is False
    assert p["allow_custom_price"] is True


def test_busqueda_sin_sesion_devuelve_401(anon_client):
    assert anon_client.get("/api/items", query_string={"q": "x"}).status_code == 401


# ---------------------------------------------------------------- precios en masa

def test_actualizar_precios_en_masa(client, db, item):
    db.add_item("222", "", "Azúcar", 5, 0, None, 50.0)
    azucar = id_por_codigo(db, "222")

    r = client.post(f"{PRODUCTS}/update_price_bulk",
                    json={"products": [{"id": item, "new_price": 90}, {"id": azucar, "new_price": 55.5}]})

    assert r.status_code == 200
    assert r.get_json()["message"] == "Precios actualizados exitosamente"
    assert client.get(f"{PRODUCTS}/{item}").get_json()["price"] == 90
    assert client.get(f"{PRODUCTS}/{azucar}").get_json()["price"] == 55.5


@pytest.mark.parametrize("cuerpo", [{}, {"products": "x"}, {"products": {"id": 1}}])
def test_precios_en_masa_con_formato_invalido(client, cuerpo):
    r = client.post(f"{PRODUCTS}/update_price_bulk", json=cuerpo)

    assert r.status_code == 400
    assert r.get_json()["error"] == "Datos inválidos"


def test_precios_en_masa_sin_id(client):
    r = client.post(f"{PRODUCTS}/update_price_bulk", json={"products": [{"new_price": 10}]})

    assert r.status_code == 400
    assert r.get_json()["error"] == "Cada producto requiere id"


@pytest.mark.parametrize("precio", [None, "90", [1]])
def test_precios_en_masa_con_precio_no_numerico(client, item, precio):
    r = client.post(f"{PRODUCTS}/update_price_bulk", json={"products": [{"id": item, "new_price": precio}]})

    assert r.status_code == 400
    assert r.get_json()["error"] == "Cada producto requiere un precio numérico"
    assert client.get(f"{PRODUCTS}/{item}").get_json()["price"] == 80.0


@pytest.mark.parametrize("precio", [-1, 1000001])
def test_precios_en_masa_fuera_de_rango(client, item, precio):
    r = client.post(f"{PRODUCTS}/update_price_bulk", json={"products": [{"id": item, "new_price": precio}]})

    assert r.status_code == 400
    assert client.get(f"{PRODUCTS}/{item}").get_json()["price"] == 80.0


def test_un_precio_invalido_en_la_lista_no_aplica_ninguno(client, db, item):
    db.add_item("222", "", "Azúcar", 5, 0, None, 50.0)
    azucar = id_por_codigo(db, "222")

    r = client.post(f"{PRODUCTS}/update_price_bulk",
                    json={"products": [{"id": item, "new_price": 90}, {"id": azucar, "new_price": -5}]})

    assert r.status_code == 400
    assert client.get(f"{PRODUCTS}/{item}").get_json()["price"] == 80.0


def test_precios_en_masa_sin_permiso_devuelve_403(vendor_client, item, sin_permisos):
    r = vendor_client.post(f"{PRODUCTS}/update_price_bulk", json={"products": [{"id": item, "new_price": 1}]})

    assert r.status_code == 403


# ---------------------------------------------------------------- stock en masa

def test_actualizar_stock_en_masa(client, item):
    r = client.post(f"{PRODUCTS}/stock_update_bulk", json={"products": [{"id": item, "new_stock": 42}]})

    assert r.status_code == 200
    assert r.get_json()["message"] == "Stock actualizado exitosamente"
    assert client.get(f"{PRODUCTS}/{item}").get_json()["stock"] == 42


def test_stock_en_masa_no_toca_productos_sin_control_de_stock(client, generic_item):
    r = client.post(f"{PRODUCTS}/stock_update_bulk", json={"products": [{"id": generic_item, "new_stock": 30}]})

    assert r.status_code == 200
    assert client.get(f"{PRODUCTS}/{generic_item}").get_json()["stock"] == 0


@pytest.mark.parametrize("cuerpo", [{}, {"products": "x"}])
def test_stock_en_masa_con_formato_invalido(client, cuerpo):
    r = client.post(f"{PRODUCTS}/stock_update_bulk", json=cuerpo)

    assert r.status_code == 400
    assert r.get_json()["error"] == "Datos inválidos"


def test_stock_en_masa_sin_id(client):
    r = client.post(f"{PRODUCTS}/stock_update_bulk", json={"products": [{"new_stock": 1}]})

    assert r.status_code == 400
    assert r.get_json()["error"] == "Cada producto requiere id"


@pytest.mark.parametrize("stock", [-1, 1.5, "10", None])
def test_stock_en_masa_con_valor_invalido(client, item, stock):
    r = client.post(f"{PRODUCTS}/stock_update_bulk", json={"products": [{"id": item, "new_stock": stock}]})

    assert r.status_code == 400
    assert r.get_json()["error"] == "Cada producto requiere un stock entero no negativo"
    assert client.get(f"{PRODUCTS}/{item}").get_json()["stock"] == 10


def test_stock_en_masa_sin_permiso_devuelve_403(vendor_client, item, sin_permisos):
    r = vendor_client.post(f"{PRODUCTS}/stock_update_bulk", json={"products": [{"id": item, "new_stock": 1}]})

    assert r.status_code == 403