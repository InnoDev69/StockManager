from flask import Blueprint, request, jsonify, session
from server.api.auth_utils import require_auth, require_role
from miscellaneous import ROLES
from server.bd.bdInstance import db

audit_api = Blueprint('audit', __name__)

def _get_filters():
    """Extrae y valida los query params comunes."""
    return {
        'action':    request.args.get('action'),
        'date_from': request.args.get('from'),
        'date_to':   request.args.get('to'),
        'limit':     request.args.get('limit', 50, type=int),
        'offset':    request.args.get('offset', 0, type=int),
    }

@audit_api.route('/user/<int:user_id>', methods=['GET'])
@require_auth
def get_user_history(user_id):
    """Obtiene el historial de un usuario específico con filtros opcionales."""
    current_user_id = session.get('user_id')
    current_role = session.get('role')

    if current_role != ROLES.ROOT and current_user_id != user_id:
        return jsonify({'error': 'Permiso denegado'}), 403

    filters = _get_filters()
    result = db.get_audit_log(user_id=user_id, **filters)

    return jsonify(result)

@audit_api.route('/all', methods=['GET'])
@require_auth
@require_role(ROLES.ROOT)
def get_all_history():
    """Obtiene el historial completo con filtros opcionales."""
    filters = _get_filters()
    result = db.get_audit_log(**filters)
    return jsonify(result)

@audit_api.route('/entity/<entity_type>/<int:entity_id>', methods=['GET'])
@require_auth
@require_role(ROLES.ROOT, ROLES.ADMIN)
def get_entity_trail(entity_type, entity_id):
    """Obtiene el historial de cambios para una entidad específica."""
    trail = db.get_entity_audit_trail(entity_type, entity_id)
    return jsonify({
        'entity_type': entity_type,
        'entity_id':   entity_id,
        'changes':     trail,
    })