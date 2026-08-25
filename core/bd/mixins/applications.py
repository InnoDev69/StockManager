from miscellaneous import logger
from core.bd.bdErrors import DatabaseError

class ApplicationsMixin:
    """Mixin para gestionar solicitudes de registro de usuarios"""

    def get_pending_applications(self, page=1, limit=10):
        """
        Obtiene solicitudes de registro pendientes con paginación.
        
        Args:
            page (int): Número de página
            limit (int): Registros por página
        
        Returns:
            dict: {
                'data': [users with application='pending'],
                'page': current_page,
                'pages': total_pages,
                'total': total_records
            }
        """
        try:
            offset = (page - 1) * limit
            
            # Total de registros
            total_rows = self.execute_query(
                "SELECT COUNT(*) FROM users WHERE application = 'pending'",
                fetch=True
            )
            total = total_rows[0][0] if total_rows else 0
            pages = (total + limit - 1) // limit
            
            # Datos de la página
            rows = self.execute_query(
                "SELECT id, username, email, created_at FROM users WHERE application = 'pending' ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
                fetch=True
            )
            
            data = [
                {
                    'id': r[0],
                    'username': r[1],
                    'email': r[2],
                    'created_at': r[3]
                }
                for r in rows
            ]
            
            return {
                'data': data,
                'page': page,
                'pages': pages,
                'total': total
            }
        except Exception as e:
            raise DatabaseError(f"Error al obtener solicitudes: {e}")

    def approve_application(self, user_id):
        """
        Aprueba una solicitud de registro.
        Actualiza application='accepted' y status=1 (activo)
        
        Args:
            user_id (int): ID del usuario
        
        Returns:
            bool: True si se aprobó
        """
        try:
            self.execute_query(
                "UPDATE users SET application = 'accepted', status = 1 WHERE id = ?",
                (user_id,),
                fetch=False
            )
            logger.info(f"[Applications] Solicitud {user_id} aprobada")
            return True
        except Exception as e:
            raise DatabaseError(f"Error al aprobar solicitud: {e}")

    def reject_application(self, user_id):
        """
        Rechaza una solicitud de registro.
        Actualiza application='rejected' (mantiene status=0)
        
        Args:
            user_id (int): ID del usuario
        
        Returns:
            bool: True si se rechazó
        """
        try:
            self.execute_query(
                "UPDATE users SET application = 'rejected' WHERE id = ?",
                (user_id,),
                fetch=False
            )
            logger.info(f"[Applications] Solicitud {user_id} rechazada")
            return True
        except Exception as e:
            raise DatabaseError(f"Error al rechazar solicitud: {e}")