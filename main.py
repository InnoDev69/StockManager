import os
import sys
import signal
import atexit
import threading
import socket
import time
from time import perf_counter

from dotenv import load_dotenv
load_dotenv()  # antes que cualquier import propio, para que lean env vars ya cargadas

from waitress import create_server
from miscellaneous import logger, SCHEDULER
from core.stockly import Stockly
from core.bd.bdInstance import db

WAITRESS_THREADS = 4
FLASK_HOST = "127.0.0.1"
FLASK_PORT = 5000
APP_LOGGER_NAME = "ROOT"

t0 = perf_counter()


class ServerManager:
    """Encapsula el estado que antes eran globals (_server, _cleanup_done)
    mutados desde el thread de waitress y leídos desde signal handlers."""

    def __init__(self, app):
        self.app = app
        self._server = None
        self._cleanup_done = False

    def run(self):
        self._server = create_server(
            self.app,
            host=FLASK_HOST,
            port=FLASK_PORT,
            threads=WAITRESS_THREADS,
            channel_timeout=30,
            cleanup_interval=10,
        )
        self._server.run()

    def wait_until_ready(self, timeout=10.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                with socket.create_connection((FLASK_HOST, FLASK_PORT), timeout=0.1):
                    return True
            except OSError:
                time.sleep(0.05)
        return False

    def cleanup(self):
        if self._cleanup_done:
            return
        self._cleanup_done = True

        logger.info("Limpiando recursos...", source=APP_LOGGER_NAME)
        SCHEDULER.stop()

        if self._server:
            self._server.close()
            self._server = None

        db.close_conn()
        from core.services import cache_service
        cache_service.flush()


def start_background_jobs():
    """Antes esto corría como side-effect de importar el módulo. Ahora se
    llama explícitamente desde __main__."""
    SCHEDULER.add_task(86400, logger._cleanup_old_logs)
    SCHEDULER.add_task(1800, db._check_unique_root_user)
    SCHEDULER.start()


def launch_desktop_app(server: ServerManager):
    if sys.platform == "linux":
        os.environ.setdefault("PYWEBVIEW_GTK", "1")
        os.environ.setdefault("WEBKIT_DISABLE_DMABUF_RENDERER", "1")
        os.environ.setdefault("WEBKIT_DISABLE_COMPOSITING_MODE", "1")
        import io, contextlib
        with contextlib.redirect_stderr(io.StringIO()):
            import webview
    else:
        import webview

    flask_thread = threading.Thread(target=server.run, daemon=True, name="waitress")
    flask_thread.start()

    if not server.wait_until_ready(timeout=15.0):
        raise RuntimeError("Waitress no respondió en 15 segundos.")

    logger.info(f"BOOT:server_ready {(perf_counter() - t0) * 1000:.0f} ms", source=APP_LOGGER_NAME)

    base_path = sys._MEIPASS if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(base_path, "static", "app", "icon.png")

    window = webview.create_window(
        "Stockly",
        f"http://{FLASK_HOST}:{FLASK_PORT}",
        width=1200, height=800, min_size=(800, 600),
    )

    if sys.platform == "linux" and os.path.exists(icon_path):
        webview.start(icon=icon_path)
    else:
        webview.start()


def run_server_only():
    logger.info(f"Sirviendo en http://{FLASK_HOST}:{FLASK_PORT} (server-only)", source=APP_LOGGER_NAME)
    server.run()


def _sigterm_as_keyboard_interrupt(signum, frame):
    raise KeyboardInterrupt()


if __name__ == "__main__":
    stockly = Stockly()
    server = ServerManager(stockly.app)

    server_only = "--server" in sys.argv or os.getenv("STOCKLY_SERVER_ONLY") == "1"

    if server_only:
        signal.signal(signal.SIGTERM, _sigterm_as_keyboard_interrupt)
        try:
            start_background_jobs()
            run_server_only()
        except KeyboardInterrupt:
            logger.info("Cerrando servidor (Ctrl+C)...", source=APP_LOGGER_NAME)
        except Exception as e:
            logger.exception(f"Error al iniciar el servidor: {e}", source=APP_LOGGER_NAME)
        finally:
            server.cleanup()

    else:
        signal.signal(signal.SIGTERM, lambda *_: (server.cleanup(), sys.exit(0)))
        signal.signal(signal.SIGINT, lambda *_: (server.cleanup(), sys.exit(0)))
        atexit.register(server.cleanup)
        try:
            start_background_jobs()
            launch_desktop_app(server)
        except Exception as e:
            logger.exception(f"Error al iniciar el servidor: {e}", source=APP_LOGGER_NAME)
        finally:
            server.cleanup()