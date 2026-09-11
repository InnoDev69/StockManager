import os
import sys
import uuid

from flask import Flask, session, render_template, request
from flask_session import Session

from miscellaneous import logger, Var, Limits, ROLES
from miscellaneous.dirs import get_data_path
from miscellaneous.permissions import PERMS
from core.api import api_bp
from core.routes import all_blueprints
from core.services import permissions_service
from core.config import config
from templates.views import View

APP_LOGGER_NAME = "ROOT"


class Stockly:
    """Application factory: arma la instancia de Flask ya lista para correr."""

    def __init__(self):
        self.is_executable = getattr(sys, "frozen", False)
        self.base_dir = self._resolve_base_dir()

        self.app = Flask(
            __name__,
            root_path=self.base_dir,
            template_folder="templates",
            static_folder="static",
        )

        self._configure_app()
        self._configure_session()
        self._configure_jinja()
        self._register_blueprints()
        self._register_error_handlers()

    def _resolve_base_dir(self):
        """Raíz real del proyecto, sin importar desde qué submódulo
        (core/stockly.py) se instancie esta clase. Compilado -> _MEIPASS."""
        if self.is_executable:
            return sys._MEIPASS
        # sube desde core/stockly.py hasta la raíz del proyecto
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Configuración de Flask: secret key, tamaño máximo de uploads, cookies, etc.

    def _configure_app(self):
        self.app.config.update(
            SECRET_KEY=os.getenv("FLASK_SECRET_KEY") or self._get_or_create_secret(),
            MAX_CONTENT_LENGTH=16 * 1024 * 1024,
            SESSION_COOKIE_SAMESITE="Lax",
            DEBUG=False,
            TESTING=False,
            TEMPLATES_AUTO_RELOAD=False,
        )

    def _get_or_create_secret(self):
        """summary_line
        
        Keyword arguments:
        argument -- description
        Return: return_description
        """
        
        secret = config.get("app.secret_key")
        if secret is None:
            secret = os.urandom(24).hex()
            config.set("app.secret_key", secret)
            logger.info("Generado nuevo secret_key de la aplicación", source=APP_LOGGER_NAME)
        return secret

    def _configure_session(self):
        self.app.config.update(
            SESSION_TYPE="filesystem",
            SESSION_FILE_DIR=get_data_path("flask_session"),
            SESSION_PERMANENT=False,
            SESSION_USE_SIGNER=True,
        )
        logger.debug(f"base_dir: {self.base_dir}", source=APP_LOGGER_NAME)
        logger.debug(f"template_folder: {self.app.template_folder}", source=APP_LOGGER_NAME)
        logger.debug(f"session_dir: {self.app.config['SESSION_FILE_DIR']}", source=APP_LOGGER_NAME)
        Session(self.app)

    # Jinja globals y filtros personalizados, disponibles en todos los templates
    def _configure_jinja(self):
        self.app.jinja_env.globals.update({
            "Limits": Limits,
            "Var": Var,
            "ROLES": ROLES,
            "IS_EXECUTABLE": self.is_executable,
            "APP_MODE": "Ejecutable" if self.is_executable else "Desarrollo",
            "has_permission": lambda perm: permissions_service.has_permission(session.get("role"), perm),
            "PERMS": PERMS,
            "View": View,
        })

    def _register_blueprints(self):
        self.app.register_blueprint(api_bp, url_prefix="/api")
        for bp in all_blueprints:
            self.app.register_blueprint(bp)

    # Error handlers: loguean y devuelven templates o JSON según corresponda

    def _register_error_handlers(self):
        self.app.errorhandler(404)(self._handle_404)
        self.app.errorhandler(500)(self._handle_server_error)
        self.app.errorhandler(Exception)(self._handle_server_error)

    def _handle_404(self, e):
        logger.warning(f"404 - Ruta no encontrada: {request.path}", source=APP_LOGGER_NAME)
        if request.path.startswith("/api"):
            return {"error": "Ruta no encontrada"}, 404
        return render_template(View.ERROR_404.value), 404

    def _handle_server_error(self, e):
        logger.error(f"Error en {request.path}: {e}", source=APP_LOGGER_NAME)
        error_id = str(uuid.uuid4())[:8].upper()
        logger.exception(f"Error {error_id} en {request.path}: {e}", source=APP_LOGGER_NAME)
        return render_template(View.ERROR_500.value, error_id=error_id, error=e), 500