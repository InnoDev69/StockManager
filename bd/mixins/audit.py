import json
import sqlite3
from datetime import datetime
from tools.logger import logger

class AuditMixin:

    def log_audit(self, actor_id, action, entity_type,
                  entity_id=None, old_value=None, new_value=None,
                  description=None, ip_address=None, status='success'):
        """
        Registra una acción. Llamar SIEMPRE desde la ruta Flask,
        nunca desde otro mixin de BD.
        """
        # Si no hay actor_id, no se puede auditar (integridad referencial)
        if not actor_id:
            logger.warning(f"[Audit] No se puede auditar sin actor_id. Acción: {action}")
            return
            
        try:
            with self._cursor() as cur:
                cur.execute("""
                    INSERT INTO audit_log
                        (user_id, action, entity_type, entity_id,
                         old_value, new_value, description,
                         ip_address, status, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    actor_id,
                    action,
                    entity_type,
                    entity_id,
                    json.dumps(old_value) if old_value else None,
                    json.dumps(new_value) if new_value else None,
                    description,
                    ip_address,
                    status,
                    datetime.now().isoformat()
                ))
        except sqlite3.Error as e:
            logger.error(f"[Audit] Error al registrar acción: {e}", exc_info=True)

    def get_audit_log(self, user_id=None, action=None,
                      date_from=None, date_to=None,
                      limit=50, offset=0):
        """
        Consulta el historial con filtros opcionales.
        Todos los parámetros son opcionales para soportar
        tanto /user/<id> como /all.
        """
        conditions = []
        params = []

        if user_id is not None:
            conditions.append("user_id = ?")
            params.append(user_id)

        if action:
            conditions.append("action = ?")
            params.append(action.upper())

        if date_from:
            conditions.append("timestamp >= ?")
            params.append(date_from)

        if date_to:
            conditions.append("timestamp <= ?")
            params.append(date_to)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        count_row = self.execute_query(
            f"SELECT COUNT(*) FROM audit_log {where}", params
        )
        total = count_row[0][0] if count_row else 0

        rows = self.execute_query(
            f"""
            SELECT al.id, al.user_id, u.username,
                   al.action, al.entity_type, al.entity_id,
                   al.description, al.timestamp, al.status
            FROM audit_log al
            JOIN users u ON u.id = al.user_id
            {where}
            ORDER BY al.timestamp DESC
            LIMIT ? OFFSET ?
            """,
            params + [limit, offset]
        )

        records = [
            {
                'id':          row[0],
                'user_id':     row[1],
                'username':    row[2],
                'action':      row[3],
                'entity_type': row[4],
                'entity_id':   row[5],
                'description': row[6],
                'timestamp':   row[7],
                'status':      row[8],
            }
            for row in rows
        ]

        return {'total': total, 'records': records}

    def get_entity_audit_trail(self, entity_type, entity_id):
        rows = self.execute_query("""
            SELECT al.user_id, u.username, al.action,
                   al.old_value, al.new_value,
                   al.timestamp, al.description
            FROM audit_log al
            JOIN users u ON u.id = al.user_id
            WHERE al.entity_type = ? AND al.entity_id = ?
            ORDER BY al.timestamp ASC
        """, (entity_type, entity_id))

        return [
            {
                'user_id':     row[0],
                'username':    row[1],
                'action':      row[2],
                'old_value':   json.loads(row[3]) if row[3] else None,
                'new_value':   json.loads(row[4]) if row[4] else None,
                'timestamp':   row[5],
                'description': row[6],
            }
            for row in rows
        ]