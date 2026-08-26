from core.routes.auth import auth_bp
from core.routes.dashboard import dashboard_bp
from core.routes.products import products_bp
from core.routes.sales import sales_bp
from core.routes.settings import settings_bp
from core.routes.users import users_bp
from core.routes.metrics import metrics_bp
from core.routes.notifications import notifications_bp
from core.routes.help import help_bp
from core.routes.changelog import changelog_bp
from core.routes.credit import credit_bp

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