import time
import sqlite3
import threading
import contextlib
from .bdErrors import *
from miscellaneous import ROLES
from miscellaneous import Var
from miscellaneous import logger

from .mixins.users import UsersMixin
from .mixins.items import ItemsMixin
from .mixins.sales import SalesMixin
from .mixins.metrics import MetricsMixin
from .mixins.password_reset import PasswordResetMixin
from .mixins.notifications import NotificationsMixin
from .mixins.applications import ApplicationsMixin
from .mixins.audit import AuditMixin
from .mixins.credit import CreditMixin
from .mixins.weight_items import WeightItemsMixin

from werkzeug.security import generate_password_hash

from .tables import tables
from .migrations import migrations
from .indexes import indexes

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
    CreditMixin,
    WeightItemsMixin,
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
    - ApplicationsMixin: gestión de solicitudes de aplicación
    - AuditMixin: registro de auditoría
    - CreditMixin: gestión de clientes y movimientos de cuenta
    - WeightItemsMixin: gestión de productos por peso
    Attributes:
        db_path (str): Ruta al archivo de base de datos SQLite
    """

    def __init__(self, db_path):
        self.db_path = db_path

    def _get_conn(self)-> sqlite3.Connection:
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

    def close_conn(self)-> None:
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

    def init_db(self)-> None:
        """
        Inicializa la base de datos creando todas las tablas e índices necesarios
        en una única transacción, y luego aplica migraciones incrementales.
        """
        

        with self._cursor() as cur:
            for table_name, table_query in tables.items():
                logger.info(f"[DB] Creando tabla '{table_name}'...")
                cur.execute(table_query)
            logger.info("[DB] Creando índices para optimizar consultas...")
        
        self._create_index()

        self.__create_default_root_user()
        self.__run_migrations()
        self.__migrate_sells_item_id_nullable()
        self._check_unique_root_user()

    def _create_index(self) -> None:
        """
        Crea todos los índices definidos en indexes.py.
        Se ejecuta dentro de la misma transacción de init_db.
        """
        with self._cursor() as cur:
            for index_name, table_name, columns in indexes:
                cur.execute(
                    f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({columns})"
                )
        logger.info(f"[DB] {len(indexes)} índices verificados/creados")
    
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
            
    def __migrate_sells_item_id_nullable(self):
        """
        Saca el NOT NULL de sells.item_id: es vestigial (la info real de
        qué se vendió vive en 'details'), y bloquea ventas 100% por peso.
        Idempotente vía PRAGMA table_info.
        """
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cur = conn.cursor()
        try:
            cur.execute("PRAGMA table_info(sells)")
            col = next((c for c in cur.fetchall() if c[1] == "item_id"), None)
            if col is None or col[3] == 0:  # col[3] = notnull flag
                logger.debug("[Migration] 'sells.item_id' ya es nullable, skip")
                return

            cur.execute("PRAGMA foreign_keys = OFF")
            cur.execute("BEGIN")
            cur.execute("""
                CREATE TABLE sells_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id INTEGER,
                    date TEXT NOT NULL,
                    vendor_id INTEGER NOT NULL REFERENCES users(id),
                    payment_method TEXT NOT NULL DEFAULT 'Efectivo',
                    customer_id INTEGER DEFAULT NULL,
                    amount_paid REAL DEFAULT NULL,
                    FOREIGN KEY (item_id) REFERENCES items (id)
                )
            """)
            cur.execute("""
                INSERT INTO sells_new
                    (id, item_id, date, vendor_id, payment_method, customer_id, amount_paid)
                SELECT id, item_id, date, vendor_id, payment_method, customer_id, amount_paid
                FROM sells
            """)
            cur.execute("DROP TABLE sells")
            cur.execute("ALTER TABLE sells_new RENAME TO sells")
            conn.commit()
            cur.execute("PRAGMA foreign_keys = ON")
            logger.info("[Migration] ✓ 'sells.item_id' ahora es nullable")
        except sqlite3.Error as e:
            conn.rollback()
            raise DatabaseError(f"Migration error (sells.item_id nullable): {e}")
        finally:
            cur.close()
            conn.close()

    def __run_migrations(self):
        """
        Aplica migraciones incrementales e idempotentes.

        Usa una conexión temporal independiente para no interferir con el pool
        de hilos. Si la migración falla por una razón distinta a "columna ya
        existe", se loggea como warning y se continúa con las demás.
        """
    
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cur = conn.cursor()
        try:
            for table, column, definition in migrations:
                try:
                    cur.execute(
                        f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
                    )
                    logger.info(f"[Migration] Columna '{column}' agregada a '{table}'")
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
        cur = conn.cursor()
        try:
            yield cur
            conn.commit()
            logger.debug(f"[DB] Transaction commit | filas={cur.rowcount} | last_id={cur.lastrowid}")
        except Exception as e:
            conn.rollback()
            logger.error(
                f"[DB] Transaction rollback | error={e}",
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
            
        Example:
            items = [(1, 'Item A', 10), (2, 'Item B', 5)]
            db.execute_many("INSERT INTO items (id, name, quantity) VALUES (?, ?, ?)", items)
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