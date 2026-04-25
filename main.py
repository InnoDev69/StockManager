import os
import sys
import signal
import uuid
import atexit
import threading
import time
import socket
from time import perf_counter

from flask import Flask, render_template, request
from dotenv import load_dotenv
from api import api_bp
from data.variables import Var
from routes import all_blueprints
from data.limits import Limits
from tools.logger import logger
from tools.scheduler import SCHEDULER
from bd.bdInstance import db
from waitress import create_server

t0 = perf_counter()
logger.info("boot:start")

load_dotenv()

# ── Configuración ─────────────────────────────────────────────────────────────

WAITRESS_THREADS = 8
FLASK_HOST = '127.0.0.1'
FLASK_PORT = 5000

# ── App Flask ─────────────────────────────────────────────────────────────────

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.getenv("FLASK_SECRET_KEY", "a")

app.config.update(
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=1800,
    DEBUG=False,
    TESTING=False,
    TEMPLATES_AUTO_RELOAD=False,
)

# ── Context processors ────────────────────────────────────────────────────────

@app.context_processor
def inject_globals():
    return {
        "Limits": Limits,
        "Var": Var,
    }

# ── Blueprints ────────────────────────────────────────────────────────────────

app.register_blueprint(api_bp, url_prefix="/api")

for bp in all_blueprints:
    app.register_blueprint(bp)

# ── Error handlers ────────────────────────────────────────────────────────────

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

# ── Servidor Waitress ─────────────────────────────────────────────────────────

_server = None

def run_waitress():
    global _server
    _server = create_server(
        app,
        host=FLASK_HOST,
        port=FLASK_PORT,
        threads=WAITRESS_THREADS,
        channel_timeout=30,
        cleanup_interval=10,
    )
    _server.run()

# ── Health check: reemplaza time.sleep(1) ────────────────────────────────────

def wait_for_server(host: str, port: int, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.1):
                return True
        except OSError:
            time.sleep(0.05)
    return False

# ── Cleanup y señales ─────────────────────────────────────────────────────────

_cleanup_done = False

def cleanup():
    global _cleanup_done, _server
    if _cleanup_done:
        return
    _cleanup_done = True

    logger.info("Limpiando recursos...")
    SCHEDULER.stop()

    if _server:
        _server.close()
        _server = None

    db.close_conn()

def signal_handler(sig, frame):
    logger.info("Señal de terminación recibida, cerrando servidor...")
    cleanup()
    sys.exit(0)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)
atexit.register(cleanup)

# ── Scheduler ─────────────────────────────────────────────────────────────────

SCHEDULER.add_task(86400, logger._cleanup_old_logs)
SCHEDULER.start()

# ── Arranque ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        logger.info("Iniciando aplicación...")

        if sys.platform == "linux":
            os.environ.setdefault("PYWEBVIEW_GTK", "1")
            os.environ.setdefault("WEBKIT_DISABLE_DMABUF_RENDERER", "1")
            import io
            import contextlib
            with contextlib.redirect_stderr(io.StringIO()):
                import webview
        else:
            import webview

        # Ruta al ícono — usa _MEIPASS si está compilado
        if getattr(sys, "frozen", False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(base_path, "static", "app", "icon.png")

        # Arrancar Waitress en hilo daemon
        flask_thread = threading.Thread(target=run_waitress, daemon=True, name="waitress")
        flask_thread.start()

        if not wait_for_server(FLASK_HOST, FLASK_PORT, timeout=15.0):
            raise RuntimeError("Waitress no respondió en 15 segundos.")

        logger.info("Servidor listo, abriendo ventana...")
        logger.info(f"boot:server_ready {(perf_counter() - t0) * 1000} ms")

        window = webview.create_window(
            "Stockly",
            f"http://{FLASK_HOST}:{FLASK_PORT}",
            width=1200,
            height=800,
            min_size=(800, 600),
        )
        
        logger.info(f"boot:window_created {(perf_counter() - t0) * 1000} ms")

        # Iniciar webview
        if sys.platform == "linux" and os.path.exists(icon_path):
            try:
                webview.start(icon=icon_path)
            except Exception as e:
                logger.warning(f"No se pudo establecer el ícono: {e}")
                webview.start()
        else:
            logger.info("Aplicación iniciada")
            webview.start()

    except Exception as e:
        logger.exception(f"Error al iniciar el servidor: {e}")
    finally:
        cleanup()