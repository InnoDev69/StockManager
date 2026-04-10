# api/notifications_api.py (nuevo archivo)
from collections import defaultdict
import json
import threading
import time
from tools.logger import logger

from flask import Blueprint, Response, jsonify, request, session
from api.auth_utils import require_admin, require_auth
from bd.bdInstance import db

notifications_api = Blueprint('notifications_api', __name__, url_prefix='/notifications')

@notifications_api.route('/unread', methods=['GET'])
@require_auth
def get_unread():
    """Obtiene notificaciones no leídas."""
    user_id = session.get('user_id')
    notifications = db.get_unread_notifications(user_id, limit=10)
    unread_count = db.get_unread_count(user_id)
    
    return jsonify({
        'notifications': notifications,
        'unread_count': unread_count
    }), 200

@notifications_api.route('/all', methods=['GET'])
@require_auth
def get_all():
    """Obtiene todas las notificaciones con paginación."""
    user_id = session.get('user_id')
    limit = request.args.get('limit', 20, type=int)
    offset = request.args.get('offset', 0, type=int)
    notifications = db.get_all_notifications(user_id, limit=limit, offset=offset)
    
    return jsonify(notifications), 200

@notifications_api.route('/<int:notification_id>/read', methods=['POST'])
@require_auth
def mark_read(notification_id):
    """Marca una notificación como leída."""
    try:
        db.mark_as_read(notification_id)
        return jsonify({"message": "Notificación marcada como leída"}), 200
    except Exception as e:
        logger.error(f"Error al marcar notificación como leída: {e}")
        return jsonify({"error": str(e)}), 500

@notifications_api.route('/read-all', methods=['POST'])
@require_auth
def mark_all_read():
    """Marca todas las notificaciones como leídas."""
    user_id = session.get('user_id')
    try:
        db.mark_all_as_read(user_id)
        return jsonify({"message": "Todas las notificaciones marcadas como leídas"}), 200
    except Exception as e:
        logger.error(f"Error al marcar todas las notificaciones como leídas: {e}")
        return jsonify({"error": str(e)}), 500
    
@notifications_api.route('/create', methods=['POST'])
@require_admin
def create_notification():
    """
        Crea una nueva notificación (solo admin).
        
        JSON body:
        {
            "user_id": 123,
            "title": "Stock bajo",
            "message": "Tu producto X está por agotarse",
            "notification_type": "warning",  # info, warning, error
            "action_url": "/products/123"  # Opcional
        }
    """
    data = request.get_json()
    title = data.get('title')
    user_id = data.get('user_id')
    message = data.get('message')
    notification_type = data.get('type', 'info')  # info, warning, error
    action_url = data.get('action_url', None)
    
    if not user_id or not message or not title:
        return jsonify({"error": "Faltan campos requeridos"}), 400
    
    try:
        db.create_notification(user_id, title ,message, notification_type, action_url)
        notify_user(user_id)
        logger.info(f"Notificación creada para el usuario {user_id}")
        return jsonify({"message": "Notificación creada exitosamente"}), 201
    except Exception as e:
        logger.error(f"Error al crear notificación: {e}")
        return jsonify({"error": str(e)}), 500
    
# Diccionario global: user_id -> Event
_user_events: dict[str, threading.Event] = defaultdict(threading.Event)

def notify_user(user_id: str):
    """Llamar esto cuando se crea una notificación."""
    _user_events[user_id].set()


@notifications_api.route('/stream', methods=['GET'])
@require_auth
def stream_notifications():
    user_id = session.get('user_id')
    last_notif_ids = set()  # Guardar IDs vistos

    def generate():
        nonlocal last_notif_ids
        
        unread = db.get_unread_notifications(user_id, limit=5)
        last_notif_ids = {n['id'] for n in unread}
        
        logger.info(f"Usuario {user_id} se ha conectado al stream. Notificaciones: {len(unread)}")
        yield f"event: init\ndata: {json.dumps({'notifications': unread, 'count': db.get_unread_count(user_id)})}\n\n"

        event = _user_events[user_id]

        while True:
            try:
                triggered = event.wait(timeout=20)

                if triggered:
                    event.clear()
                    # Obtener últimas notificaciones
                    unread = db.get_unread_notifications(user_id, limit=10)
                    
                    # Encontrar nuevas (que no hemos visto antes)
                    new_notifs = [n for n in unread if n['id'] not in last_notif_ids]
                    
                    if new_notifs:
                        # Enviar evento 'notification' para cada una nueva
                        for notif in new_notifs:
                            yield f"event: notification\ndata: {json.dumps({'notification': notif})}\n\n"
                            last_notif_ids.add(notif['id'])
                    
                    # Siempre enviar 'update' con el conteo actualizado (para base.html)
                    yield f"event: update\ndata: {json.dumps({'notifications': unread[:5], 'count': db.get_unread_count(user_id)})}\n\n"
                else:
                    yield ": heartbeat\n\n"

            except GeneratorExit:
                logger.info(f"Cliente {user_id} desconectado del stream")
                break

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
        }
    )