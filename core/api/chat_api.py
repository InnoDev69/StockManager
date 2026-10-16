from pathlib import Path

from flask import Blueprint, jsonify, request, session

from stockbot.bot import StocklyBot
from core.bd.bdInstance import db
from core.api.auth_utils import require_role

from core.services import SERVICE_MANAGER
from core.services.service_manager import Service  # ajustá el import a donde tengas la clase
from miscellaneous import logger
from core.config import config

chat_bp = Blueprint("chat", __name__, url_prefix="/chat")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
INTENTS_PATH = PROJECT_ROOT / "stockbot" / "intents.json"
UNRECOGNIZED_PATH = PROJECT_ROOT / "stockbot" / "unrecognized.json"

BOT_SERVICE_NAME = "stockbot"
CATALOG_REFRESH_SECONDS = 60

_bot = None


# ---------------------------------------------------------------------------
# Acciones del bot (funciones comunes, se registran al construir el bot)
# ---------------------------------------------------------------------------

def consultar_stock(entities, session):
    producto = entities["producto"]

    rows = db.execute_query(
        """
        SELECT name, quantity
        FROM items
        WHERE lower(name) = lower(?)
          AND status = 1
        LIMIT 1
        """,
        (producto,),
    )

    if not rows:
        return f"No encontré el producto '{producto}' en el inventario."

    name, quantity = rows[0]

    if quantity <= 0:
        return f"{name} está agotado."

    return f"Hay {quantity} unidades de {name} disponibles."


def consultar_precio(entities, session):
    producto = entities["producto"]

    rows = db.execute_query(
        """
        SELECT name, price
        FROM items
        WHERE lower(name) = lower(?)
          AND status = 1
        LIMIT 1
        """,
        (producto,),
    )

    if not rows:
        return f"No encontré el producto '{producto}' en el inventario."

    name, price = rows[0]
    return f"El precio de {name} es ${float(price):,.2f}."


def listar_productos(entities, session):
    rows = db.execute_query(
        """
        SELECT name, quantity, price
        FROM items
        WHERE status = 1
        ORDER BY name ASC
        """
    )

    if not rows:
        return "No hay productos disponibles en el inventario."

    response_lines = ["Estos son los productos disponibles en tu inventario actual:"]
    for name, quantity, price in rows:
        response_lines.append(f"- {name}: {quantity} unidades, ${float(price):,.2f}")

    return "\n".join(response_lines)


BOT_ACTIONS = {
    "consultar_stock": consultar_stock,
    "consultar_precio": consultar_precio,
    "listar_productos": listar_productos,
}


# ---------------------------------------------------------------------------
# Ciclo de vida del bot
# ---------------------------------------------------------------------------

def _build_bot():
    new_bot = StocklyBot(
        intents_path=str(INTENTS_PATH),
        product_catalog=[],
        unrecognized_log_path=str(UNRECOGNIZED_PATH),
    )
    for action_name, action_fn in BOT_ACTIONS.items():
        new_bot.register_action(action_name)(action_fn)
    return new_bot


def _refresh_catalog(target_bot):
    product_rows = db.execute_query("SELECT name FROM items WHERE status = 1")
    if product_rows is not None:
        target_bot.product_catalog = [row[0] for row in product_rows if row and row[0]]


def bot_background_worker(stop_event):
    """
    Crea el bot al activarse, mantiene su catálogo actualizado mientras
    el servicio corre y lo descarta al desactivarse.
    """
    global _bot

    try:
        local_bot = _build_bot()
    except Exception:
        logger.exception("No se pudo crear el bot.")
        return

    try:
        # Primera carga del catálogo antes de publicar el bot,
        # así nunca responde con el catálogo vacío.
        try:
            _refresh_catalog(local_bot)
        except Exception as e:
            logger.exception(f"Error al actualizar el catálogo de productos: {e}")

        _bot = local_bot

        while not stop_event.wait(CATALOG_REFRESH_SECONDS):
            try:
                _refresh_catalog(local_bot)
            except Exception as e:
                logger.exception(f"Error al actualizar el catálogo de productos: {e}")
    finally:
        _bot = None


# Registro del servicio (tolerante a imports repetidos)
try:
    SERVICE_MANAGER.register_service(Service(BOT_SERVICE_NAME, bot_background_worker))
except ValueError:
    pass


# ---------------------------------------------------------------------------
# Control del bot (se usa desde código, sin endpoints)
# ---------------------------------------------------------------------------

def start_bot():
    """Activa el bot. Devuelve True si lo arrancó, False si ya estaba activo."""
    try:
        SERVICE_MANAGER.start_service(BOT_SERVICE_NAME)
    except RuntimeError:
        return False
    return True


def stop_bot(timeout=5):
    """Desactiva el bot. Devuelve True si se detuvo a tiempo."""
    return SERVICE_MANAGER.stop_service(BOT_SERVICE_NAME, timeout)


def bot_is_running():
    """True si el hilo del servicio está vivo (aunque todavía no esté listo)."""
    return SERVICE_MANAGER.is_running(BOT_SERVICE_NAME)


def bot_is_ready():
    """True si el bot ya está instanciado y puede responder mensajes."""
    return _bot is not None


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

@chat_bp.post("")
@require_role()
def chat():
    current_bot = _bot  # referencia local: no cambia a mitad de la request
    if current_bot is None:
        return jsonify({"error": "El bot está desactivado. Activalo desde la configuracion en las funciones experimentales."}), 503

    payload = request.get_json(silent=True) or {}
    message = (payload.get("message") or "").strip()

    if not message:
        return jsonify({"error": "El mensaje no puede estar vacío"}), 400

    session_id = payload.get("session_id") or str(session["user_id"])

    result = current_bot.ask(message, session_id=session_id)

    return jsonify(result)


if config.get("experimental_features.CHAT_BOT_FEATURE", default=False):
    start_bot()