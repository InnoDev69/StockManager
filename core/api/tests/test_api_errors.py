"""
Tests del manejo global de errores (core/stockly.py): la API siempre responde
JSON y con el código HTTP que corresponde, nunca con la página HTML de error 500.
"""


def test_ruta_inexistente_en_la_api_devuelve_404_en_json(client):
    r = client.get("/api/esta-ruta-no-existe")

    assert r.status_code == 404
    assert r.get_json() == {"error": "Ruta no encontrada"}


def test_metodo_no_permitido_devuelve_405_en_json(client):
    r = client.delete("/api/sales/bulk")

    assert r.status_code == 405
    assert r.get_json() == {"error": "Método no permitido"}


def test_un_error_inesperado_devuelve_500_en_json_con_id_de_referencia(client, monkeypatch, item):
    def explota(*args, **kwargs):
        raise RuntimeError("falla inesperada")

    # Falla fuera de los try/except de la vista (en el decorador de auditoría):
    # llega al manejador global de errores
    monkeypatch.setattr("miscellaneous.audit_decorator.get_client_ip", explota)

    r = client.post("/api/sales/bulk", json={"items": [{"item_id": item, "quantity": 1}]})

    assert r.status_code == 500
    cuerpo = r.get_json()
    assert cuerpo["error"] == "Error interno del servidor"
    assert len(cuerpo["error_id"]) == 8
