from flask import Blueprint, request, jsonify, session
from tools.logger import logger, get_current_log_file
import json

debug_bp = Blueprint('debug', __name__, url_prefix='/api/debug')

def require_admin():
    if not session.get("user_id"):
        return False

    return True

@debug_bp.route('/log', methods=['POST'])
def log_client_error():
    """Captura logs desde JavaScript del cliente."""
    if not require_admin():
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    level = data.get('level', 'info').upper()
    message = data.get('message', '')
    context = data.get('context', {})
    timestamp = data.get('timestamp', '')
    
    log_msg = f"[JS CLIENT] {message} | Context: {json.dumps(context)}"
    
    if level == 'ERROR':
        logger.error(log_msg)
    elif level == 'WARNING':
        logger.warning(log_msg)
    elif level == 'INFO':
        logger.info(log_msg)
    else:
        logger.debug(log_msg)
    
    return jsonify({'status': 'logged'}), 200

@debug_bp.route('/logs', methods=['GET'])
def get_recent_logs():
    """Obtiene logs recientes para el panel de debug."""
    if not require_admin():
        return jsonify({'error': 'Unauthorized'}), 401
    
    log_file = get_current_log_file()
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        recent = lines[-100:] if len(lines) > 100 else lines
        return jsonify({'logs': recent}), 200
    except:
        return jsonify({'logs': [], 'error': 'No logs available'}), 200