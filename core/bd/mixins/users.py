from core.bd.bdErrors import DatabaseError
from miscellaneous import ROLES
from miscellaneous import logger
from miscellaneous import Var

class UsersMixin:
    """Métodos de gestión de usuarios. Requiere que la clase base tenga execute_query()."""

    def user_exists(self, username, email):
        """
        Verifica si un usuario ya existe por nombre o email.

        Args:
            username (str): Nombre de usuario a verificar
            email (str): Email a verificar

        Returns:
            bool: True si existe un usuario con ese username o email
        """
        rows = self.execute_query(
            "SELECT id FROM users WHERE username = ? OR email = ?",
            (username, email),
        )
        return bool(rows)

    def add_user(self, username, password, email, role=ROLES.VENDOR, status=0, application=Var.USER_APPLICATION_PENDING):
        """
        Registra un nuevo usuario en el sistema.

        Args:
            username (str): Nombre de usuario único
            password (str): Contraseña hasheada (NO texto plano)
            email (str): Correo electrónico
            role (str): Rol del usuario ('admin' o 'vendedor' o 'root', default: ROLES.VENDOR)
            status (int): Estado del usuario
            application (str): Estado de la aplicación

        Raises:
            DatabaseError: Si el usuario ya existe o hay un error SQL

        Warning:
            NUNCA pasar contraseñas en texto plano. Hashear antes de llamar.
        """
        try:
            if self.user_exists(username, email):
                logger.info("Usuario o email ya existe")
                return
            self.execute_query(
                "INSERT INTO users (username, password, email, role, status, application) VALUES (?, ?, ?, ?, ?, ?)",
                (username, password, email, role, status, application),
                fetch=False,
            )
        except Exception as e:
            raise DatabaseError(f"Error al agregar usuario: {e}")

    def get_user_by_email(self, email):
        """
        Busca un usuario por su email.

        Args:
            email (str): Email del usuario

        Returns:
            tuple|None: (id, username, password_hash, role) o None si no existe
        """
        rows = self.execute_query(
            "SELECT id, username, password, role FROM users WHERE email = ?",
            (email,),
        )
        return rows[0] if rows else None
    
    def get_username_by_id(self, user_id):
        """
        Busca un usuario por su ID.

        Args:
            user_id (int): ID del usuario

        Returns:
            str|None: Nombre de usuario o None si no existe
        """
        rows = self.execute_query(
            "SELECT username FROM users WHERE id = ?",
            (user_id,),
        )
        return rows[0][0] if rows else None