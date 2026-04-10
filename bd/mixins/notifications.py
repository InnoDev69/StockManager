from tools.local_time import localDate

class NotificationsMixin:
    """Gestión de notificaciones del sistema."""
    
    def create_notification(self, user_id, title, message, notification_type='info', action_url=None):
        """
        Crea una notificación.
        
        notification_type: 'info', 'warning', 'success', 'error'
        """
        self.execute_query("""
            INSERT INTO notifications 
            (user_id, title, message, type, action_url, is_read, created_at)
            VALUES (?, ?, ?, ?, ?, 0, ?)
        """, (user_id, title, message, notification_type, action_url, localDate()))
    
    def get_unread_notifications(self, user_id, limit=5):
        """Obtiene notificaciones no leídas."""
        rows = self.execute_query("""
            SELECT id, title, message, type, action_url, created_at
            FROM notifications
            WHERE user_id = ? AND is_read = 0
            ORDER BY created_at DESC
            LIMIT ?
        """, (user_id, limit))
        return [dict(zip(['id', 'title', 'message', 'type', 'action_url', 'created_at'], row)) 
                for row in rows] if rows else []
    
    def get_all_notifications(self, user_id, limit=20, offset=0):
        """Obtiene todas las notificaciones con paginación."""
        rows = self.execute_query("""
            SELECT id, title, message, type, is_read, action_url, created_at
            FROM notifications
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """, (user_id, limit, offset))
        return [dict(zip(['id', 'title', 'message', 'type', 'is_read', 'action_url', 'created_at'], row)) 
                for row in rows] if rows else []
    
    def mark_as_read(self, notification_id):
        """Marca notificación como leída."""
        self.execute_query(
            "UPDATE notifications SET is_read = 1 WHERE id = ?",
            (notification_id,)
        )
    
    def mark_all_as_read(self, user_id):
        """Marca todas las notificaciones como leídas."""
        self.execute_query(
            "UPDATE notifications SET is_read = 1 WHERE user_id = ?",
            (user_id,)
        )
    
    def get_unread_count(self, user_id):
        """Cuenta notificaciones no leídas."""
        rows = self.execute_query(
            "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0",
            (user_id,)
        )
        return rows[0][0] if rows else 0