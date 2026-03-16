import os
import sys
import signal
import uuid
import webview
from flask import Flask, render_template, request
from dotenv import load_dotenv

from api import api_bp
from routes import all_blueprints
from data.limits import Limits
from tools.logger import logger
from tools.scheduler import SCHEDULER

load_dotenv()

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.getenv("FLASK_SECRET_KEY", "a")

# --- Context processors ---
@app.context_processor
def inject_limits():
    return {"Limits": Limits}

# --- Registra blueprints ---
app.register_blueprint(api_bp, url_prefix="/api")
for bp in all_blueprints:
    app.register_blueprint(bp)

# --- Error handlers ---
@app.errorhandler(404)
def page_not_found(e):
    logger.warning(f"404 - Ruta no encontrada: {request.path}")
    return render_template("404.html"), 404

@app.errorhandler(500)
def internal_error(e):
    error_id = str(uuid.uuid4())[:8].upper()
    logger.error(f"Internal server error {error_id}: {e}", exc_info=True)
    return render_template("500.html", error_id=error_id, error=e), 500

@app.errorhandler(Exception)
def handle_exception(e):
    error_id = str(uuid.uuid4())[:8].upper()
    logger.exception(f"Excepción no capturada en {request.path}: {str(e)}")
    return render_template("500.html", error_id=error_id, error=e), 500

# --- Señales ---
def signal_handler(sig, frame):
    logger.info("Señal de terminación recibida, cerrando servidor...")
    sys.exit(0)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

# --- Scheduler ---
SCHEDULER.add_task(86400, logger._cleanup_old_logs)
SCHEDULER.start()

# --- Arranque ---
if __name__ == "__main__":
    try:
        logger.info("Iniciando aplicación...")

        if sys.platform == "linux":
            os.environ["WEBKIT_DISABLE_DMABUF_RENDERER"] = "1"

        app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
        app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
        app.config["PERMANENT_SESSION_LIFETIME"] = 1800

        if getattr(sys, "frozen", False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))

        icon_path = os.path.join(base_path, "static", "app", "icon.png")

        window = webview.create_window("Stockly", app, width=1200, height=800)

        if sys.platform == "linux" and os.path.exists(icon_path):
            try:
                webview.start(icon=icon_path)
            except Exception as e:
                logger.warning(f"No se pudo establecer el ícono: {str(e)}")
                webview.start()
        else:
            logger.info("Aplicación iniciada")
            webview.start()
    except Exception as e:
        logger.exception(f"Error al iniciar el servidor: {str(e)}")