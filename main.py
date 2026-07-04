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
from data.roles import ROLES

from config import config  # Asegura que se carguen los módulos de configuración
from services import backup_service

t0 = perf_counter()
logger.info("boot:start", source="ROOT")

load_dotenv()

# ── Configuración ─────────────────────────────────────────────────────────────

WAITRESS_THREADS = 8
FLASK_HOST = '127.0.0.1'
FLASK_PORT = 5000
APP_LOGGER_NAME = "ROOT"

# ── App Flask ─────────────────────────────────────────────────────────────────

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.getenv("FLASK_SECRET_KEY", "a")

app.config.update(
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,
    SESSION_COOKIE_SAMESITE="Lax",
    DEBUG=False,
    TESTING=False,
    TEMPLATES_AUTO_RELOAD=False,
)

# ── Context processors ────────────────────────────────────────────────────────
IS_EXECUTABLE = getattr(sys, 'frozen', False)

@app.context_processor
def inject_globals():
    return {
        "Limits": Limits,
        "Var": Var,
        "ROLES": ROLES,
        'IS_EXECUTABLE': IS_EXECUTABLE,
        'APP_MODE': 'Ejecutable' if IS_EXECUTABLE else 'Desarrollo'
    }

# ── Blueprints ────────────────────────────────────────────────────────────────

app.register_blueprint(api_bp, url_prefix="/api")

for bp in all_blueprints:
    app.register_blueprint(bp)

# ── Error handlers ────────────────────────────────────────────────────────────

@app.errorhandler(404)
def page_not_found(e):
    logger.warning(f"[{APP_LOGGER_NAME}] 404 - Ruta no encontrada: {request.path}")
    if request.path.startswith("/api"):
        return {"error": "Ruta no encontrada"}, 404
    return render_template("404.html"), 404

@app.errorhandler(500)
def internal_error(e):
    error_id = str(uuid.uuid4())[:8].upper()
    logger.error(f"[{APP_LOGGER_NAME}] Internal server error {error_id}: {e}", exc_info=True)
    return render_template("500.html", error_id=error_id, error=e), 500

@app.errorhandler(Exception)
def handle_exception(e):
    error_id = str(uuid.uuid4())[:8].upper()
    logger.exception(f"[{APP_LOGGER_NAME}] Excepción no capturada en {request.path}: {str(e)}")
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

    logger.info(f"[{APP_LOGGER_NAME}] Limpiando recursos...")
    SCHEDULER.stop()

    if _server:
        _server.close()
        _server = None

    db.close_conn()

def signal_handler(sig, frame):
    logger.info(f"[{APP_LOGGER_NAME}] Señal de terminación recibida, cerrando servidor...")
    cleanup()
    sys.exit(0)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)
atexit.register(cleanup)

def show_message_box(title, message, type="error"):
    import tkinter as tk
    from tkinter import messagebox
    
    root = tk.Tk()
    root.withdraw()  # Oculta la ventana principal
    
    if type == "error":
        messagebox.showerror(title, message)
    else:
        messagebox.showinfo(title, message)
    root.destroy()

def handle_dll_exception():
    import subprocess
    
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)  # Compilado con PyInstaller
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))  # Script normal

    internal_dir = os.path.join(base_dir, "_internal")

    if not os.path.exists(internal_dir):
        logger.error(f"Directorio no encontrado: {internal_dir}")
        return

    ps_command = (
        f'Get-ChildItem "{internal_dir}" -Recurse | '
        'Unblock-File -ErrorAction SilentlyContinue'
    )
    
    try:
        resultado = subprocess.run(
            ["powershell", "-Command", ps_command],
            capture_output=True,
            text=True,
            # creationflags=subprocess.CREATE_NO_WINDOW  # Descomenta para ocultar la ventana
        )

        if resultado.returncode == 0:
            logger.info(f"[{APP_LOGGER_NAME}] Archivos desbloqueados correctamente.")
            show_message_box("Corrección aplicada", "Se ha aplicado una corrección para resolver el error de DLL. Por favor, reinicia la aplicación.", type="info")
        else:
            show_message_box("Error al aplicar corrección", "No se pudo aplicar la corrección automática. Por favor, desbloquea manualmente los archivos en el directorio '_internal' y reinicia la aplicación.", type="error")
            logger.error(f"[{APP_LOGGER_NAME}] El comando terminó con errores: {resultado.stderr}")

    except Exception as e:
        logger.error(f"[{APP_LOGGER_NAME}] Error al ejecutar PowerShell: {e}")

# ── Scheduler ─────────────────────────────────────────────────────────────────

def app_uptime():
    return time.time() - t0

SCHEDULER.add_task(86400, logger._cleanup_old_logs)
SCHEDULER.add_task(1800, db._check_unique_root_user)

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

        logger.info(f"[{APP_LOGGER_NAME}] Servidor listo, abriendo ventana...")
        logger.info(f"[{APP_LOGGER_NAME}] boot:server_ready {(perf_counter() - t0) * 1000} ms")

        window = webview.create_window(
            "Stockly",
            f"http://{FLASK_HOST}:{FLASK_PORT}",
            width=1200,
            height=800,
            min_size=(800, 600),
        )
        
        logger.info(f"[{APP_LOGGER_NAME}] boot:window_created {(perf_counter() - t0) * 1000} ms")

        # Iniciar webview
        if sys.platform == "linux" and os.path.exists(icon_path):
            try:
                webview.start(icon=icon_path)
            except Exception as e:
                logger.warning(f"[{APP_LOGGER_NAME}]No se pudo establecer el ícono: {e}")
                webview.start()
        else:
            logger.info(f"[{APP_LOGGER_NAME}] Aplicación iniciada")
            webview.start()
    except RuntimeError as e:
        if "Failed to resolve Python.Runtime.Loader.Initialize" in str(e):
            logger.warning(f"[{APP_LOGGER_NAME}]Falta Python.Runtime.Loader.Initialize, intentando resolver...")
            handle_dll_exception()
    except Exception as e:
        logger.exception(f"[{APP_LOGGER_NAME}] Error al iniciar el servidor: {e}")
        show_message_box("Error al iniciar el servidor", f"[{APP_LOGGER_NAME}] Error al iniciar el servidor: {e}", type="error")
    finally:
        cleanup()