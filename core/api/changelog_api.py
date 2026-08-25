from flask import Blueprint, jsonify, request
from core.services.changelog_service import fetch_changelog

changelog_bp = Blueprint("changelog", __name__)

@changelog_bp.route("/changelog", methods=["GET"])
def get_changelog():
    """
    Endpoint para obtener el changelog de la última versión.
    """

    changelog = fetch_changelog()
    if changelog is None:
        return jsonify({"error": "No se pudo obtener el changelog"}), 503

    return jsonify({"changelog": changelog})