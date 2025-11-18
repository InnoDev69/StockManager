from flask import Blueprint, jsonify, request

api_bp = Blueprint("api", __name__)

@api_bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200