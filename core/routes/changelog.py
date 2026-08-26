from flask import Blueprint, render_template, session

from miscellaneous import ROLES

changelog_bp = Blueprint('changelog', __name__)

@changelog_bp.route('/changelog')
def changelog_view():
    return render_template('changelogs.html', role=session.get("role", ROLES.VENDOR), show_back=False)