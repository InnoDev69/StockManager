from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.products import products_bp
from routes.sales import sales_bp
from routes.settings import settings_bp
from routes.users import users_bp
from routes.metrics import metrics_bp
from routes.notifications import notifications_bp

all_blueprints = [
    auth_bp,
    dashboard_bp,
    products_bp,
    sales_bp,
    settings_bp,
    users_bp,
    metrics_bp,
    notifications_bp,
]