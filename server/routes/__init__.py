from server.routes.auth import auth_bp
from server.routes.dashboard import dashboard_bp
from server.routes.products import products_bp
from server.routes.sales import sales_bp
from server.routes.settings import settings_bp
from server.routes.users import users_bp
from server.routes.metrics import metrics_bp
from server.routes.notifications import notifications_bp
from server.routes.help import help_bp
from server.routes.changelog import changelog_bp
from server.routes.credit import credit_bp

all_blueprints = [
    auth_bp,
    dashboard_bp,
    products_bp,
    sales_bp,
    settings_bp,
    users_bp,
    metrics_bp,
    notifications_bp,
    help_bp,
    changelog_bp,
    credit_bp
]