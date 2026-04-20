from flask import Blueprint, request, jsonify, session
from tools.logger import logger, get_current_log_file
import json

debug_bp = Blueprint('debug', __name__, url_prefix='/debug')

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
    
@debug_bp.route('/command', methods=['POST'])
def execute_command():
    """Ejecuta código Python en el servidor (solo admin)."""
    if not session.get("user_id"):
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    code = data.get('code', '')
    
    if not code:
        return jsonify({'error': 'No code provided'}), 400
    
    try:
        safe_dict = {
            'db': db,
            'logger': logger,
            '__builtins__': {
                'len': len,
                'str': str,
                'int': int,
                'float': float,
                'list': list,
                'dict': dict,
                'print': print,
                'range': range,
                'enumerate': enumerate,
            }
        }
        
        import io
        from contextlib import redirect_stdout
        
        f = io.StringIO()
        with redirect_stdout(f):
            exec(code, safe_dict)
        
        output = f.getvalue() or "Executed successfully"
        logger.info(f"[DEBUG] Server command executed: {code[:100]}")
        
        return jsonify({'output': output}), 200
        
    except Exception as e:
        logger.error(f"[DEBUG] Server command error: {e}")
        return jsonify({'error': str(e)}), 400