from flask import Blueprint, jsonify

health_api = Blueprint("health_api", __name__)

@health_api.route("/health", methods=["GET"])
def health():
    """Endpoint de verificación de salud del servidor."""
    return jsonify({"status": "Ok"}), 200