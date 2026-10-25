from flask import Blueprint, render_template, session
from templates.views import View

from miscellaneous import ROLES

changelog_bp = Blueprint('changelog', __name__)

@changelog_bp.route('/changelog')
def changelog_view():
    return render_template(View.CHANGELOGS.value, role=session.get("role", ROLES.VENDOR), show_back=False)