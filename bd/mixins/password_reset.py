
class PasswordResetMixin:
    """Métodos de recuperación de contraseña."""

    def save_reset_code(self, email, code):
        """
        Guarda un código de recuperación para un usuario.

        Args:
            email (str): Email del usuario
            code (str): Código de recuperación a guardar
        """
        self.execute_query(
            "INSERT INTO password_resets (email, code, created_at) VALUES (?, ?, datetime('now'))",
            (email, code),
            fetch=False,
        )

    def get_reset_code(self, email):
        """
        Obtiene el código de recuperación más reciente para un email.

        Args:
            email (str): Email del usuario

        Returns:
            tuple: (code, created_at) o (None, None) si no existe
        """
        rows = self.execute_query(
            "SELECT code, created_at FROM password_resets WHERE email = ? ORDER BY created_at DESC LIMIT 1",
            (email,),
        )
        return rows[0] if rows else (None, None)

    def delete_reset_code(self, email):
        """
        Elimina los códigos de recuperación asociados a un email.

        Args:
            email (str): Email del usuario
        """
        self.execute_query(
            "DELETE FROM password_resets WHERE email = ?",
            (email,),
            fetch=False,
        )

    def update_user_password(self, email, new_password):
        """
        Actualiza la contraseña de un usuario identificado por su email.

        Args:
            email (str): Email del usuario
            new_password (str): Nueva contraseña hasheada
        """
        self.execute_query(
            "UPDATE users SET password = ? WHERE email = ?",
            (new_password, email),
            fetch=False,
        )

    def verify_code(self, email, code):
        """
        Verifica si el código de recuperación es válido (< 15 minutos).

        Args:
            email (str): Email del usuario
            code (str): Código de recuperación a verificar

        Returns:
            bool: True si el código es válido
        """
        rows = self.execute_query(
            "SELECT 1 FROM password_resets WHERE email = ? AND code = ? AND created_at > datetime('now', '-15 minutes')",
            (email, code),
        )
        return bool(len(rows) > 0)