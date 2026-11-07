"""Actualizaciones de Stockly. Ver `service.UpdateService`."""
from __future__ import annotations

from .service import UpdateError, UpdateInfo, UpdateService

_service: UpdateService | None = None


class _LoggerAdapter:
    """Adapta el logger de Stockly (info/warning/error con `source`)."""

    def __init__(self, logger):
        self._logger = logger

    def info(self, message):
        self._logger.info(message, source="UPDATER")

    def warning(self, message):
        self._logger.warning(message, source="UPDATER")

    def error(self, message):
        self._logger.error(message, source="UPDATER")


def init_app_updates(app, *, license_manager=None) -> UpdateService:
    """Crea el servicio y lo deja disponible para las rutas /api/updates."""
    global _service
    from miscellaneous import get_data_path, logger
    from .api import EXTENSION_KEY

    _service = UpdateService(
        get_data_path(), license_manager=license_manager, log=_LoggerAdapter(logger),
    )
    app.extensions[EXTENSION_KEY] = _service
    return _service


def get_update_service() -> UpdateService | None:
    return _service


def register_shutdown_hook(hook) -> None:
    """Indica cómo cerrar Stockly de forma ordenada cuando hay que actualizar."""
    if _service is not None:
        _service.set_shutdown_hook(hook)


__all__ = ["UpdateError", "UpdateInfo", "UpdateService", "get_update_service",
           "init_app_updates", "register_shutdown_hook"]
