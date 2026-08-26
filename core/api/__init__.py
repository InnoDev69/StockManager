from flask import Blueprint

api_bp = Blueprint("api", __name__)

from core.api.products_api import products_api
from core.api.sales_api import sales_api
from core.api.users_api import users_api
from core.api.metrics_api import metrics_api
from core.api.notifications_api import notifications_api
from core.api.settings_api import settings_api
from core.api.debug_api import debug_bp
from core.api.applications_api import applications_api
from core.api.audit_api import audit_api
from core.api.feature_highlights import bp as feature_highlights_bp
from core.api.changelog_api import changelog_bp
from core.api.credit_api import credit_api

api_bp.register_blueprint(products_api)
api_bp.register_blueprint(sales_api)
api_bp.register_blueprint(users_api)
api_bp.register_blueprint(metrics_api)
api_bp.register_blueprint(notifications_api)
api_bp.register_blueprint(settings_api)
api_bp.register_blueprint(debug_bp)
api_bp.register_blueprint(applications_api)
api_bp.register_blueprint(audit_api)
api_bp.register_blueprint(feature_highlights_bp)
api_bp.register_blueprint(changelog_bp)
api_bp.register_blueprint(credit_api)