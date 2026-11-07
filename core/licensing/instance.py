"""Licencias en la app: manager único y registro de rutas.

Si la librería `stockly_license` no está instalada o no hay clave pública
embebida (`public_keys.py`), las licencias quedan DESACTIVADAS y Stockly
funciona como antes (sin restricciones ni pestaña de licencia).
"""
from __future__ import annotations

_manager = None
_checked = False


def get_license_manager():
    """LicenseManager de la app, o None si las licencias no están habilitadas."""
    global _manager, _checked
    if _checked:
        return _manager
    _checked = True
    try:
        from miscellaneous import get_data_path
        from .manager import LicenseManager
        from .public_keys import build_verifier
        _manager = LicenseManager(get_data_path(), build_verifier())
    except ImportError:
        _manager = None          # falta stockly_license
    except RuntimeError:
        _manager = None          # no hay clave pública embebida
    return _manager


def init_app_licensing(app):
    """Registra /api/license y los helpers de plantillas. Devuelve el manager o None."""
    manager = get_license_manager()
    enabled = manager is not None
    app.context_processor(lambda: {"license_enabled": enabled})
    if not enabled:
        return None
    from core.api.auth_utils import require_role
    from miscellaneous import ROLES
    from .flask_integration import init_licensing
    init_licensing(app, manager, auth_decorator=require_role(ROLES.ADMIN, ROLES.ROOT))
    return manager
