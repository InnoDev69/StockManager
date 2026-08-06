from flask import Blueprint, render_template, session
from miscellaneous import ROLES
from server.api.auth_utils import require_role, require_auth

credit_bp = Blueprint("credit_bp", __name__)

@require_auth
@credit_bp.route("/customers")
def create_customer():
    return render_template('credit.html', role=session.get("role", ROLES.VENDOR), show_back=False)