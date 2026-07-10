import time
import sqlite3
import threading
import contextlib
from bd.bdErrors import *
from data.roles import ROLES
from data.variables import Var
from tools.logger import logger
from tools.timmer import measure_time

from bd.mixins.users import UsersMixin
from bd.mixins.items import ItemsMixin
from bd.mixins.sales import SalesMixin
from bd.mixins.metrics import MetricsMixin
from bd.mixins.password_reset import PasswordResetMixin
from bd.mixins.notifications import NotificationsMixin
from bd.mixins.applications import ApplicationsMixin
from bd.mixins.audit import AuditMixin
from werkzeug.security import generate_password_hash

_thread_local = threading.local()


class BDConector(
    UsersMixin,
    ItemsMixin,
    SalesMixin,
    MetricsMixin,
    PasswordResetMixin,
    NotificationsMixin,
    ApplicationsMixin,
    AuditMixin,
):
    """
    Conector de base de datos SQLite con gestión automática de transacciones.

    Los métodos de dominio están organizados en mixins:
    - UsersMixin: gestión de usuarios
    - ItemsMixin: gestión de productos/inventario
    - SalesMixin: registro y consulta de ventas
    - MetricsMixin: métricas y reportes
    - PasswordResetMixin: recuperación de contraseña
    - NotificationsMixin: gestión de notificaciones
    Attributes:
        db_path (str): Ruta al archivo de base de datos SQLite
    """

    def __init__(self, db_path):
        self.db_path = db_path

    def _get_conn(self):
        """
        Retorna la conexión SQLite del hilo actual, creándola si no existe.

        Reutiliza la misma conexión durante toda la vida del hilo, evitando
        el overhead de abrir/cerrar una conexión por cada query.

        Returns:
            sqlite3.Connection: Conexión activa con PRAGMAs configurados
        """
        conn = getattr(_thread_local, "conn", None)
        if conn is None:
            try:
                conn = sqlite3.connect(self.db_path, check_same_thread=False)
                conn.execute("PRAGMA foreign_keys = ON")
                conn.execute("PRAGMA journal_mode = WAL")
                conn.execute("PRAGMA synchronous = NORMAL")
                conn.execute("PRAGMA cache_size = -8000")
                conn.execute("PRAGMA temp_store = MEMORY")
                _thread_local.conn = conn
                logger.debug("[DB] Nueva conexión creada para el hilo")
            except sqlite3.OperationalError as e:
                if "unable to open database file" in str(e).lower():
                    logger.error(
                        f"[DB] Archivo de base de datos no encontrado en {self.db_path}: {e}",
                        exc_info=True,
                    )
                    raise DatabaseError(f"Database file not found at {self.db_path}")
                raise DatabaseError(f"Error al conectar a la base de datos: {e}")
            except sqlite3.Error as e:
                logger.error(f"[DB] Error al conectar: {e}", exc_info=True)
                raise DatabaseError(f"Error connecting to database: {e}")
        return conn

    def close_conn(self):
        """
        Cierra la conexión del hilo actual y la elimina del pool.

        Debe llamarse al final de cada request en Flask:
            @app.teardown_appcontext
            def close_db(exception=None):
                db.close_conn()
        """
        conn = getattr(_thread_local, "conn", None)
        if conn is not None:
            conn.close()
            _thread_local.conn = None
            logger.debug("[DB] Conexión del hilo cerrada")

    @contextlib.contextmanager
    def _cursor(self):
        """
        Context manager para ejecutar consultas con transacciones automáticas.

        Reutiliza la conexión del hilo actual. Hace commit si todo sale bien,
        rollback si ocurre un error de SQLite, y siempre libera el cursor.
        """
        conn = self._get_conn()
        start = time.perf_counter()
        cur = conn.cursor()
        try:
            yield cur
            conn.commit()
            elapsed = (time.perf_counter() - start) * 1000
            logger.debug(
                f"[DB] Commit | filas={cur.rowcount} | "
                f"last_id={cur.lastrowid} | tiempo={elapsed:.2f}ms"
            )
        except sqlite3.Error as e:
            conn.rollback()
            elapsed = (time.perf_counter() - start) * 1000
            logger.error(
                f"[DB] Rollback | error={e} | tiempo={elapsed:.2f}ms",
                exc_info=True,
            )
            raise DatabaseError(f"Database error: {e}")
        finally:
            cur.close()

    def init_db(self):
        """
        Inicializa la base de datos creando todas las tablas e índices necesarios
        en una única transacción, y luego aplica migraciones incrementales.
        """
        users_table_query = """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            role TEXT NOT NULL,
            status INTEGER NOT NULL DEFAULT 1,
            application TEXT NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            history TEXT
        )
        """
        items_table_query = """
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY NOT NULL,
            barrs_code TEXT UNIQUE,
            description TEXT,
            name TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0,
            min_quantity INTEGER NOT NULL DEFAULT 5,
            price REAL NOT NULL,
            expiration_date TEXT,
            status INTEGER NOT NULL DEFAULT 1,
            notified_low_stock INTEGER NOT NULL DEFAULT 0,
            created_at TEXT,
            updated_at TEXT
        )
        """
        sells_table_query = """
        CREATE TABLE IF NOT EXISTS sells (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            vendor_id INTEGER NOT NULL REFERENCES users(id),
            payment_method TEXT NOT NULL DEFAULT 'Efectivo',
            FOREIGN KEY (item_id) REFERENCES items (id)
        )
        """
        sells_details_table_query = """
        CREATE TABLE IF NOT EXISTS details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sell_id INTEGER NOT NULL,
            item_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            vendor_id INTEGER NOT NULL REFERENCES users(id),
            payment_method TEXT NOT NULL DEFAULT 'Efectivo',
            FOREIGN KEY (sell_id) REFERENCES sells (id),
            FOREIGN KEY (item_id) REFERENCES items (id)
        )
        """
        reset_codes_table_query = """
        CREATE TABLE IF NOT EXISTS password_resets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            code TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        item_attributes_table_query = """
        CREATE TABLE IF NOT EXISTS item_attributes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            code TEXT NOT NULL UNIQUE,
            data_type TEXT NOT NULL,
            required INTEGER NOT NULL DEFAULT 0,
            status INTEGER NOT NULL DEFAULT 1
        )
        """
        item_attribute_values_table_query = """
        CREATE TABLE IF NOT EXISTS item_attribute_values (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            attribute_id INTEGER NOT NULL,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(item_id, attribute_id),
            FOREIGN KEY (item_id) REFERENCES items(id),
            FOREIGN KEY (attribute_id) REFERENCES item_attributes(id)
        )
        """

        notifications_table_query = """
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            message TEXT,
            type TEXT DEFAULT 'info' CHECK(type IN ('info', 'warning', 'success', 'error')),
            action_url TEXT,
            is_read INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """

        audit_log_table_query = """
            CREATE TABLE IF NOT EXISTS audit_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                action      TEXT    NOT NULL,
                entity_type TEXT    NOT NULL,
                entity_id   INTEGER,
                old_value   TEXT,
                new_value   TEXT,
                description TEXT,
                ip_address  TEXT,
                timestamp   TEXT    DEFAULT CURRENT_TIMESTAMP,
                status      TEXT    DEFAULT 'success',
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """

        with self._cursor() as cur:
            cur.execute(users_table_query)
            cur.execute(items_table_query)
            cur.execute(sells_table_query)
            cur.execute(sells_details_table_query)
            cur.execute(reset_codes_table_query)
            cur.execute(item_attributes_table_query)
            cur.execute(item_attribute_values_table_query)
            cur.execute(notifications_table_query)
            cur.execute(audit_log_table_query)
            logger.info("[DB] Creando índices para optimizar consultas...")

            # Índice compuesto para las queries de ventas filtradas por fecha y vendedor
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_sells_date_vendor_id
                ON sells(date, vendor_id)
            """)
            # Índice individual de fecha para queries sin filtro de vendedor
            cur.execute("CREATE INDEX IF NOT EXISTS idx_sells_date ON sells(date)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_sells_vendor_id ON sells(vendor_id)")
            # Índice para consultas de ventas filtradas por producto
            cur.execute("CREATE INDEX IF NOT EXISTS idx_sells_item_id ON sells(item_id)")

            cur.execute("CREATE INDEX IF NOT EXISTS idx_details_sell_id ON details(sell_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_details_item_id ON details(item_id)")

            cur.execute("CREATE INDEX IF NOT EXISTS idx_items_name ON items(name)")
            # Índice para listados de inventario filtrados por status y ordenados por nombre
            cur.execute("CREATE INDEX IF NOT EXISTS idx_items_status_name ON items(status, name)")

            cur.execute("CREATE INDEX IF NOT EXISTS idx_notifications_user_read ON notifications(user_id, is_read)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_notifications_created ON notifications(created_at DESC)")

            # Índices para la página de auditoría: filtros por usuario, entidad y orden por fecha
            cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_user_id ON audit_log(user_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_log(entity_type, entity_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp DESC)")

        self.__create_default_root_user()
        self.__run_migrations()
        self._check_unique_root_user()

    def _check_unique_root_user(self):
        """
        Verifica que solo exista un usuario con rol ROOT.

        Si se detecta más de un usuario ROOT, se loggea un error crítico y se
        lanza una excepción para evitar inconsistencias graves en la gestión de
        usuarios.
        """
        rows = self.execute_query(
            "SELECT COUNT(*) FROM users WHERE role = ?",
            (ROLES.ROOT,),
        )
        if rows and rows[0][0] > 1: # type: ignore
            logger.critical("Múltiples usuarios con rol ROOT detectados")
            raise DatabaseError("Multiple ROOT users detected, database integrity compromised")

    def __create_default_root_user(self):
        """
        Crea un usuario root por defecto si no existe ninguno.

        Esto asegura que siempre haya al menos un usuario administrador para
        acceder al sistema después de la inicialización.
        """
        try:
            if self.execute_query("SELECT id FROM users WHERE role = ?",(ROLES.ROOT,)):
                logger.info("Usuario root ya existe, skip su creación", source="DB")
                return
            self.add_user(
                username="root",
                password=generate_password_hash("root1234"),
                email="root@root.com",
                role=ROLES.ROOT,
                status=1,
                application=Var.USER_APPLICATION_ACCEPTED
            )
        except DatabaseError as e:
            logger.error(f"Error al crear usuario root: {e}", source="DB")

    def __run_migrations(self):
        """
        Aplica migraciones incrementales e idempotentes.

        Usa una conexión temporal independiente para no interferir con el pool
        de hilos. Si la migración falla por una razón distinta a "columna ya
        existe", se loggea como warning y se continúa con las demás.
        """
        migrations = [
            ("sells",   "vendedor",       "TEXT NOT NULL DEFAULT 'unknown'"),
            ("sells",   "payment_method", "TEXT NOT NULL DEFAULT 'Efectivo'"),
            ("details", "vendedor",       "TEXT NOT NULL DEFAULT 'unknown'"),
            ("details", "payment_method", "TEXT NOT NULL DEFAULT 'Efectivo'"),
            ("users",   "status",         "INTEGER NOT NULL DEFAULT 1"),
            ("users",   "created_at",     "TEXT DEFAULT NULL"),
            ("sells",   "date",           "TEXT NOT NULL"),
            ("items", "expiration_date", "TEXT"),
            ("items", "id", "INTEGER PRIMARY KEY NOT NULL"),
            ("items", "notified_low_stock", "INTEGER NOT NULL DEFAULT 0"),
            ("items", "created_at", "TEXT"),
            ("items", "updated_at", "TEXT"),
            ("sells",   "vendor_id",       "INTEGER DEFAULT NULL"),
            ("details", "vendor_id",       "INTEGER DEFAULT NULL"),
            ("users",   "history",         "TEXT"),
            ("users",   "application",     "TEXT NOT NULL DEFAULT 'accepted'"),
            ("users", "application", "TEXT NOT NULL DEFAULT 'accepted'"),
            ("users", "username", "TEXT NOT NULL"),
            ("users", "id", "INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE"),
            ("users", "email", "TEXT NOT NULL UNIQUE"),
        ]
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cur = conn.cursor()
        try:
            for table, column, definition in migrations:
                try:
                    cur.execute(
                        f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
                    )
                    logger.info(f"[Migration] ✓ Columna '{column}' agregada a '{table}'")
                except sqlite3.OperationalError as e:
                    if "duplicate column name" in str(e).lower():
                        logger.debug(
                            f"[Migration] '{column}' en '{table}' ya existe, skip"
                        )
                    else:
                        logger.warning(
                            f"[Migration] Error inesperado en '{table}.{column}': {e}"
                        )
            conn.commit()
            logger.info("[Migration] Migraciones completadas")
        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"[Migration] Error general, rollback: {e}", exc_info=True)
            raise DatabaseError(f"Migration error: {e}")
        finally:
            cur.close()
            conn.close()
            logger.debug("[Migration] Conexión temporal cerrada")

    @contextlib.contextmanager
    def transaction(self):
        """
        Agrupa múltiples queries en una transacción explícita.

        Usar cuando un caso de uso requiere varios inserts/updates atómicos,
        por ejemplo un bulk sale. Reutiliza la conexión del hilo.

        Ejemplo:
            with self.transaction() as cur:
                cur.execute("INSERT INTO sells ...")
                cur.execute("UPDATE items SET quantity ...")
        """
        conn = self._get_conn()
        start = time.perf_counter()
        cur = conn.cursor()
        try:
            yield cur
            conn.commit()
            elapsed = (time.perf_counter() - start) * 1000
            logger.debug(f"[DB] Transaction commit | tiempo={elapsed:.2f}ms")
        except Exception as e:
            conn.rollback()
            elapsed = (time.perf_counter() - start) * 1000
            logger.error(
                f"[DB] Transaction rollback | error={e} | tiempo={elapsed:.2f}ms",
                exc_info=True,
            )
            raise
        finally:
            cur.close()

    def execute_many(self, query, params_list):
        """
        Ejecuta múltiples inserts/updates en una única transacción.

        Mucho más eficiente que llamar execute_query() en un loop,
        ya que hace un solo commit para toda la lista.

        Args:
            query (str): Consulta SQL con placeholders (?)
            params_list (list[tuple]): Lista de tuplas de parámetros

        Returns:
            int: Total de filas afectadas
        """
        with self._cursor() as cur:
            cur.executemany(query, params_list)
            logger.debug(
                f"[DB] executemany | filas={cur.rowcount} | query={query}"
            )
            return cur.rowcount

    def create_table(self, table_name, columns):
        """Crea una tabla personalizada (IF NOT EXISTS)."""
        cols_with_types = ", ".join(
            [f"{col} {dtype}" for col, dtype in columns.items()]
        )
        query = f"CREATE TABLE IF NOT EXISTS {table_name} ({cols_with_types})"
        with self._cursor() as cur:
            cur.execute(query)

    def get_count(self, query: str, params: tuple = ()) -> int:
        """Extrae el COUNT de una query de forma segura."""
        result = self.execute_query(query, params)
        return result[0][0] if result else 0

    def get_single_row(self, query: str, params: tuple = ()):
        """Obtiene una sola fila o retorna None."""
        result = self.execute_query(query, params)
        return result[0] if result else None

    def get_all_rows(self, query: str, params: tuple = ()):
        """Obtiene todas las filas (alias para clarity)."""
        return self.execute_query(query, params)

    @measure_time
    def execute_query(self, query, params=(), fetch=True):
        """
        Ejecuta una consulta SQL arbitraria con parámetros seguros.

        Args:
            query (str): Consulta SQL con placeholders (?)
            params (tuple): Valores para los placeholders
            fetch (bool): Si True retorna resultados, si False retorna filas afectadas

        Returns:
            list[tuple]: Resultados como lista de tuplas (si fetch=True)
            int: Número de filas afectadas (si fetch=False)
        """
        with self._cursor() as cur:
            cur.execute(query, params)
            if fetch:
                logger.debug(f"Executed query: {query} with params: {params}", source="DB")
                return cur.fetchall()
            logger.debug(
                f"Rows affected: {cur.rowcount} for query: {query} with params: {params}",
                source="DB"
            )
            return cur.rowcount