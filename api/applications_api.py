from flask import Blueprint, request, session, jsonify
from bd.bdInstance import db
from data.roles import ROLES
from api.auth_utils import require_auth, require_role
from tools.audit_decorator import audit_action

applications_api = Blueprint('applications_api', __name__, url_prefix='')

@applications_api.route('/applications', methods=['GET'])
@require_auth
@require_role(ROLES.ADMIN, ROLES.ROOT)
def get_applications():
    """
    Obtiene solicitudes de registro pendientes.
    Solo accesible por ADMIN o ROOT.
    
    Query params:
        page (int): Número de página (default: 1)
        limit (int): Registros por página (default: 10)
    """
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 10))
        
        result = db.get_pending_applications(page=page, limit=limit)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@applications_api.route('/applications/<int:user_id>/approve', methods=['POST'])
@require_auth
@require_role(ROLES.ADMIN, ROLES.ROOT)
@audit_action("application", "approve", "user_id")
def approve_application(user_id):
    """
    Aprueba una solicitud de registro.
    Solo accesible por ADMIN o ROOT.
    
    URL params:
        user_id (int): ID del usuario
    """
    try:
        db.approve_application(user_id)
        return jsonify({'message': 'Solicitud aprobada'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@applications_api.route('/applications/<int:user_id>/reject', methods=['POST'])
@require_auth
@require_role(ROLES.ADMIN, ROLES.ROOT)
@audit_action("application", "reject", "user_id")
def reject_application(user_id):
    """
    Rechaza una solicitud de registro.
    Solo accesible por ADMIN o ROOT.
    
    URL params:
        user_id (int): ID del usuario
    """
    try:
        db.reject_application(user_id)
        return jsonify({'message': 'Solicitud rechazada'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500