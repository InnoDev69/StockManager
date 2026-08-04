from miscellaneous import ROLES
from flask import Blueprint, render_template, session
from server.api.auth_utils import require_auth
from server.bd.bdInstance import db

notifications_bp = Blueprint('notifications', __name__)

@notifications_bp.route('/notifications')
@require_auth
def notifications_history():
    user_id = session.get('user_id')
    notifications = db.get_all_notifications(user_id, limit=100)
    return render_template('notifications.html', notifications=notifications, role=session.get('role', ROLES.VENDOR))