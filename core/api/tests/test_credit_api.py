"""
Tests de la API de cuenta corriente (core/api/credit_api.py):
clientes, saldo, movimientos, pagos y ajustes.
"""
import pytest

CUSTOMERS = "/api/customers"


def crear_cliente(client, **cuerpo):
    cuerpo.setdefault("name", "Ana")
    r = client.post(CUSTOMERS, json=cuerpo)
    assert r.status_code == 201, r.get_json()
    return r.get_json()["customer_id"]


def fiar(client, item, cliente, cantidad=2):
    """Deja al cliente debiendo cantidad * $80 (precio del fixture 'item')."""
    r = client.post(
        "/api/sales/bulk",
        json={"items": [{"item_id": item, "quantity": cantidad}],
              "payment_method": "Fiado", "customer_id": cliente},
    )
    assert r.status_code == 201, r.get_json()


# ---------------------------------------------------------------- crear cliente

def test_crear_cliente_devuelve_201_y_queda_con_saldo_cero(client, db):
    r = client.post(CUSTOMERS, json={"name": "  Ana  ", "phone": "1122334455", "credit_limit": 500})

    assert r.status_code == 201
    body = r.get_json()
    assert body["ok"] is True
    b = client.get(f"{CUSTOMERS}/{body['customer_id']}/balance").get_json()
    assert b["name"] == "Ana"            # se recorta el nombre
    assert b["phone"] == "1122334455"
    assert b["credit_limit"] == 500.0
    assert b["balance"] == 0


def test_crear_cliente_sin_limite_ni_telefono(client):
    cliente = crear_cliente(client, name="Beto")

    b = client.get(f"{CUSTOMERS}/{cliente}/balance").get_json()
    assert b["phone"] is None
    assert b["credit_limit"] is None


@pytest.mark.parametrize("cuerpo", [{}, {"name": ""}, {"name": "   "}, {"phone": "123"}])
def test_crear_cliente_sin_nombre_se_rechaza(client, cuerpo):
    r = client.post(CUSTOMERS, json=cuerpo)

    assert r.status_code == 400
    assert r.get_json()["error"] == "El nombre es requerido"


def test_crear_cliente_con_limite_negativo_se_rechaza(client):
    r = client.post(CUSTOMERS, json={"name": "Ana", "credit_limit": -1})

    assert r.status_code == 400
    assert r.get_json()["error"] == "El límite de crédito no puede ser negativo"


def test_crear_cliente_con_limite_no_numerico_se_rechaza(client):
    r = client.post(CUSTOMERS, json={"name": "Ana", "credit_limit": "mucho"})

    assert r.status_code == 400
    assert r.get_json()["error"] == "credit_limit debe ser un número"


def test_crear_cliente_con_json_roto_se_trata_como_vacio(client):
    r = client.post(CUSTOMERS, data='{"name": ', content_type="application/json")

    assert r.status_code == 400
    assert r.get_json()["error"] == "El nombre es requerido"


def test_crear_cliente_sin_sesion_devuelve_401(anon_client):
    r = anon_client.post(CUSTOMERS, json={"name": "Ana"})

    assert r.status_code == 401


# ---------------------------------------------------------------- listar

def test_listar_clientes_con_su_saldo(client, db, item):
    ana = crear_cliente(client, name="Ana", credit_limit=1000)
    crear_cliente(client, name="Beto")
    fiar(client, item, ana)

    r = client.get(CUSTOMERS)

    assert r.status_code == 200
    por_nombre = {c["name"]: c for c in r.get_json()["data"]}
    assert set(por_nombre) == {"Ana", "Beto"}
    assert por_nombre["Ana"]["balance"] == 160.0
    assert por_nombre["Beto"]["balance"] == 0


def test_listar_clientes_filtra_por_nombre(client):
    crear_cliente(client, name="Ana")
    crear_cliente(client, name="Beto")

    r = client.get(CUSTOMERS, query_string={"q": "bet"})

    assert [c["name"] for c in r.get_json()["data"]] == ["Beto"]


def test_listar_clientes_sin_resultados_devuelve_lista_vacia(client):
    r = client.get(CUSTOMERS, query_string={"q": "nadie"})

    assert r.status_code == 200
    assert r.get_json() == {"data": []}


def test_un_vendedor_puede_listar_clientes(vendor_client, db):
    db.create_customer("Ana", None, 100)

    r = vendor_client.get(CUSTOMERS)

    assert r.status_code == 200
    assert len(r.get_json()["data"]) == 1


def test_listar_clientes_sin_sesion_devuelve_401(anon_client):
    assert anon_client.get(CUSTOMERS).status_code == 401


# ---------------------------------------------------------------- saldo

def test_saldo_de_un_cliente_inexistente(client):
    r = client.get(f"{CUSTOMERS}/99999/balance")

    assert r.status_code == 404
    assert r.get_json()["error"] == "Cliente no encontrado"


def test_saldo_refleja_una_venta_fiada(client, db, item):
    cliente = crear_cliente(client, credit_limit=1000)
    fiar(client, item, cliente)

    r = client.get(f"{CUSTOMERS}/{cliente}/balance")

    assert r.status_code == 200
    assert r.get_json()["balance"] == 160.0
    assert r.get_json()["customer_id"] == cliente


# ---------------------------------------------------------------- movimientos

def test_movimientos_de_un_cliente_inexistente(client):
    r = client.get(f"{CUSTOMERS}/99999/movements")

    assert r.status_code == 404


def test_movimientos_incluyen_la_venta_y_el_pago(client, db, item):
    cliente = crear_cliente(client, credit_limit=1000)
    fiar(client, item, cliente)
    client.post(f"{CUSTOMERS}/{cliente}/payments", json={"amount": 60, "note": "adelanto"})

    r = client.get(f"{CUSTOMERS}/{cliente}/movements")

    assert r.status_code == 200
    movimientos = r.get_json()["data"]
    assert len(movimientos) == 2
    assert {m["note"] for m in movimientos} >= {"adelanto"}
    assert {m["amount"] for m in movimientos} >= {60.0}


def test_movimientos_respeta_el_limite(client, db):
    cliente = crear_cliente(client)
    for _ in range(3):
        client.post(f"{CUSTOMERS}/{cliente}/adjustments", json={"amount": 10, "note": "x"})

    r = client.get(f"{CUSTOMERS}/{cliente}/movements", query_string={"limit": 2})

    assert len(r.get_json()["data"]) == 2


@pytest.mark.parametrize("limit", [0, -5])
def test_movimientos_con_limite_menor_a_uno_se_corrige_a_uno(client, db, limit):
    cliente = crear_cliente(client)
    for _ in range(3):
        client.post(f"{CUSTOMERS}/{cliente}/adjustments", json={"amount": 10, "note": "x"})

    r = client.get(f"{CUSTOMERS}/{cliente}/movements", query_string={"limit": limit})

    assert len(r.get_json()["data"]) == 1


# ---------------------------------------------------------------- pagos

def test_pago_parcial_baja_el_saldo(client, db, item):
    cliente = crear_cliente(client, credit_limit=1000)
    fiar(client, item, cliente)

    r = client.post(f"{CUSTOMERS}/{cliente}/payments", json={"amount": 100})

    assert r.status_code == 201
    assert r.get_json()["ok"] is True
    assert "movement_id" in r.get_json()
    assert db.get_customer_balance(cliente) == 60.0


def test_pago_total_deja_el_saldo_en_cero(client, db, item):
    cliente = crear_cliente(client, credit_limit=1000)
    fiar(client, item, cliente)

    r = client.post(f"{CUSTOMERS}/{cliente}/payments", json={"amount": 160})

    assert r.status_code == 201
    assert db.get_customer_balance(cliente) == 0


def test_pago_mayor_al_saldo_se_rechaza_y_no_cambia_nada(client, db, item):
    cliente = crear_cliente(client, credit_limit=1000)
    fiar(client, item, cliente)

    r = client.post(f"{CUSTOMERS}/{cliente}/payments", json={"amount": 9999})

    assert r.status_code == 400
    assert r.get_json()["ok"] is False
    assert db.get_customer_balance(cliente) == 160.0


@pytest.mark.parametrize("cuerpo", [{}, {"amount": None}, {"amount": "abc"}, {"amount": [1]}])
def test_pago_con_monto_invalido(client, db, item, cuerpo):
    cliente = crear_cliente(client, credit_limit=1000)
    fiar(client, item, cliente)

    r = client.post(f"{CUSTOMERS}/{cliente}/payments", json=cuerpo)

    assert r.status_code == 400
    assert r.get_json()["error"] == "Monto inválido"
    assert db.get_customer_balance(cliente) == 160.0


#@pytest.mark.xfail(strict=True, reason="db.register_payment lanza DatabaseError y la API lo traduce a 500; un monto <= 0 debería dar 400")
@pytest.mark.parametrize("monto", [0, -10])
def test_pago_con_monto_no_positivo_deberia_dar_400(client, db, item, monto):
    cliente = crear_cliente(client, credit_limit=1000)
    fiar(client, item, cliente)

    r = client.post(f"{CUSTOMERS}/{cliente}/payments", json={"amount": monto})

    assert r.status_code == 400
    assert db.get_customer_balance(cliente) == 160.0


def test_pago_a_un_cliente_inexistente(client):
    r = client.post(f"{CUSTOMERS}/99999/payments", json={"amount": 10})

    assert r.status_code == 404
    assert r.get_json()["error"] == "Cliente no encontrado"


def test_pago_registra_al_usuario_que_lo_cobro(client, db, item):
    cliente = crear_cliente(client, credit_limit=1000)
    fiar(client, item, cliente)
    client.post(f"{CUSTOMERS}/{cliente}/payments", json={"amount": 10})

    movimientos = client.get(f"{CUSTOMERS}/{cliente}/movements").get_json()["data"]

    pago = next(m for m in movimientos if m["amount"] == 10.0)
    assert pago["user_id"] == 1   # root


def test_pago_sin_sesion_devuelve_401(anon_client):
    r = anon_client.post(f"{CUSTOMERS}/1/payments", json={"amount": 10})

    assert r.status_code == 401


# ---------------------------------------------------------------- ajustes

def test_ajuste_con_nota_se_registra(client, db):
    cliente = crear_cliente(client)

    r = client.post(f"{CUSTOMERS}/{cliente}/adjustments", json={"amount": 30, "note": "error de carga"})

    assert r.status_code == 201
    assert r.get_json()["ok"] is True
    movimientos = client.get(f"{CUSTOMERS}/{cliente}/movements").get_json()["data"]
    assert [m["note"] for m in movimientos] == ["error de carga"]
    assert abs(db.get_customer_balance(cliente)) == 30.0


def test_ajuste_negativo_es_valido(client, db):
    cliente = crear_cliente(client)

    r = client.post(f"{CUSTOMERS}/{cliente}/adjustments", json={"amount": -30, "note": "descuento"})

    assert r.status_code == 201
    assert abs(db.get_customer_balance(cliente)) == 30.0


@pytest.mark.parametrize("nota", [None, "", "   "])
def test_ajuste_sin_nota_se_rechaza(client, db, nota):
    cliente = crear_cliente(client)

    r = client.post(f"{CUSTOMERS}/{cliente}/adjustments", json={"amount": 30, "note": nota})

    assert r.status_code == 400
    assert r.get_json()["error"] == "El ajuste requiere una nota"
    assert db.get_customer_balance(cliente) == 0


@pytest.mark.parametrize("monto", [None, "abc"])
def test_ajuste_con_monto_invalido(client, db, monto):
    cliente = crear_cliente(client)

    r = client.post(f"{CUSTOMERS}/{cliente}/adjustments", json={"amount": monto, "note": "x"})

    assert r.status_code == 400
    assert r.get_json()["error"] == "Monto inválido"


def test_ajuste_a_un_cliente_inexistente(client):
    r = client.post(f"{CUSTOMERS}/99999/adjustments", json={"amount": 1, "note": "x"})

    assert r.status_code == 404


def test_ajuste_sin_sesion_devuelve_401(anon_client):
    r = anon_client.post(f"{CUSTOMERS}/1/adjustments", json={"amount": 1, "note": "x"})

    assert r.status_code == 401


# ---------------------------------------------------------------- actualizar cliente

def test_actualizar_nombre_y_telefono(client):
    cliente = crear_cliente(client, name="Ana", phone="111", credit_limit=500)

    r = client.post(f"{CUSTOMERS}/{cliente}", json={"name": "Ana María", "phone": "222"})

    assert r.status_code == 200
    b = client.get(f"{CUSTOMERS}/{cliente}/balance").get_json()
    assert (b["name"], b["phone"]) == ("Ana María", "222")


def test_actualizar_sin_la_clave_credit_limit_no_toca_el_limite(client):
    cliente = crear_cliente(client, credit_limit=500)

    r = client.post(f"{CUSTOMERS}/{cliente}", json={"name": "Otra"})

    assert r.status_code == 200
    b = client.get(f"{CUSTOMERS}/{cliente}/balance").get_json()
    assert b["name"] == "Otra"
    assert b["credit_limit"] == 500.0


@pytest.mark.parametrize("valor", [None, ""])
def test_actualizar_con_credit_limit_null_o_vacio_quita_el_limite(client, valor):
    cliente = crear_cliente(client, credit_limit=500)

    r = client.post(f"{CUSTOMERS}/{cliente}", json={"credit_limit": valor})

    assert r.status_code == 200
    assert client.get(f"{CUSTOMERS}/{cliente}/balance").get_json()["credit_limit"] is None


def test_actualizar_el_limite_de_credito(client):
    cliente = crear_cliente(client, credit_limit=500)

    client.post(f"{CUSTOMERS}/{cliente}", json={"credit_limit": 900})

    assert client.get(f"{CUSTOMERS}/{cliente}/balance").get_json()["credit_limit"] == 900.0


def test_actualizar_con_credit_limit_invalido(client):
    cliente = crear_cliente(client, credit_limit=500)

    r = client.post(f"{CUSTOMERS}/{cliente}", json={"credit_limit": "abc"})

    assert r.status_code == 400
    assert r.get_json()["error"] == "credit_limit inválido"
    assert client.get(f"{CUSTOMERS}/{cliente}/balance").get_json()["credit_limit"] == 500.0


#@pytest.mark.xfail(strict=True, reason="db.update_customer lanza DatabaseError('No se proporcionaron campos') y la API lo traduce a 500; debería dar 400")
@pytest.mark.parametrize("cuerpo", [{}, {"name": "", "phone": ""}])
def test_actualizar_sin_ningun_dato_deberia_dar_400(client, cuerpo):
    cliente = crear_cliente(client)

    r = client.post(f"{CUSTOMERS}/{cliente}", json=cuerpo)

    assert r.status_code == 400


def test_actualizar_un_cliente_inexistente(client):
    r = client.post(f"{CUSTOMERS}/99999", json={"name": "X"})

    assert r.status_code == 404
    assert r.get_json()["error"] == "Cliente no encontrado"


def test_actualizar_cliente_sin_sesion_devuelve_401(anon_client):
    r = anon_client.post(f"{CUSTOMERS}/1", json={"name": "X"})

    assert r.status_code == 401