"""Actualizaciones: /api/updates/status, /check y /apply (solo admin/root)."""
from core.api.auth_utils import require_role
from core.updater.api import create_updates_blueprint
from miscellaneous import ROLES

updates_api = create_updates_blueprint(require_role(ROLES.ADMIN, ROLES.ROOT))
