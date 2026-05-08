from flask import Blueprint, render_template

errors_bp = Blueprint('errors', __name__)

@errors_bp.route("/error/403")
def error_403():
    return render_template("403.html"), 403