"""
Ejemplo de integración del StocklyBot con Flask.

Ejecutar:
    pip install -r requirements.txt
    python app.py

Probar:
    curl -X POST http://localhost:5000/chat \
         -H "Content-Type: application/json" \
         -d '{"session_id": "user-123", "message": "cuanto stock hay de zapatillas"}'
"""
from pathlib import Path

from flask import Flask, jsonify, request

try:
    # cuando se importa como parte del paquete (ej. python -m stockly_bot.app)
    from .bot import StocklyBot
except ImportError:
    # cuando se corre directamente (python app.py) desde adentro de la carpeta
    from bot import StocklyBot

app = Flask(__name__)

# --- 1. Instanciar el bot -------------------------------------------------
# En la app real, el catálogo de productos debería venir de tu base de datos
# (podés cargarlo dinámicamente al iniciar el server o refrescarlo periódicamente).
INTENTS_PATH = Path(__file__).parent / "intents.json"

bot = StocklyBot(
    intents_path=str(INTENTS_PATH),
    product_catalog=["zapatillas", "remeras", "pantalones", "camperas"],
)

# --- 2. Registrar las acciones reales de tu app ---------------------------
# Reemplazar estos stubs por llamadas a tu backend/ORM real.

FAKE_STOCK_DB = {"zapatillas": 12, "remeras": 40, "pantalones": 5, "camperas": 0}
FAKE_PRICE_DB = {"zapatillas": 25000, "remeras": 8000, "pantalones": 15000, "camperas": 32000}


@bot.register_action("consultar_stock")
def consultar_stock(entities, session):
    producto = entities.get("producto")
    stock = FAKE_STOCK_DB.get(producto)
    if stock is None:
        return f"No encontré el producto '{producto}' en el catálogo."
    return f"Quedan {stock} unidades de {producto}."


@bot.register_action("consultar_precio")
def consultar_precio(entities, session):
    producto = entities.get("producto")
    precio = FAKE_PRICE_DB.get(producto)
    if precio is None:
        return f"No tengo el precio de '{producto}' cargado."
    return f"El precio de {producto} es ${precio}."


@bot.register_action("crear_pedido")
def crear_pedido(entities, session):
    producto = entities.get("producto")
    cantidad = entities.get("cantidad", "1")
    # acá iría la llamada real, ej: pedidos_service.crear(producto, cantidad, usuario=...)
    return f"Pedido creado: {cantidad} unidad(es) de {producto}. ✅"


@bot.register_action("listar_productos")
def listar_productos(entities, session):
    return "Productos disponibles: " + ", ".join(FAKE_STOCK_DB.keys())


# --- 3. Endpoint del chat ---------------------------------------------------

@app.route("/chat", methods=["POST"])
def chat():
    payload = request.get_json(silent=True) or {}
    message = (payload.get("message") or "").strip()
    session_id = payload.get("session_id") or request.remote_addr or "anon"

    if not message:
        return jsonify({"error": "El campo 'message' es requerido"}), 400

    result = bot.ask(message, session_id=session_id)
    return jsonify(result)


# --- 4. Endpoint opcional para "enseñarle" frases nuevas al bot ------------
# Útil para un panel de administración donde revisás las preguntas no
# reconocidas (quedan en unrecognized.jsonl) y las asignás a una intención.

@app.route("/train", methods=["POST"])
def train():
    payload = request.get_json(silent=True) or {}
    intent_name = payload.get("intent")
    phrase = payload.get("phrase")
    if not intent_name or not phrase:
        return jsonify({"error": "Se requieren 'intent' y 'phrase'"}), 400
    try:
        bot.add_training_phrase(intent_name, phrase)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"status": "ok", "intent": intent_name, "phrase": phrase})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
