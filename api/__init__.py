from flask import Blueprint

api_bp = Blueprint("api", __name__)

from api.products_api import products_api
from api.sales_api import sales_api
from api.users_api import users_api
from api.metrics_api import metrics_api
from api.notifications_api import notifications_api
from api.settings_api import settings_api
from api.debug_api import debug_bp
from api.applications_api import applications_api
from api.audit_api import audit_api
from api.feature_highlights import bp as feature_highlights_bp
from api.changelog_api import changelog_bp

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
