import time
import sqlite3
import contextlib
from flask import jsonify
from bd.bdErrors import *
from tools.timmer import measure_time
from tools.logger import logger
from data.validators import ItemValidator, UserValidator, ValidationError

from bd.mixins.users import UsersMixin
from bd.mixins.items import ItemsMixin
from bd.mixins.sales import SalesMixin
from bd.mixins.metrics import MetricsMixin
from bd.mixins.password_reset import PasswordResetMixin

class BDConector(
    UsersMixin,
    ItemsMixin,
    SalesMixin,
    MetricsMixin,
    PasswordResetMixin,
):
    """
    Conector de base de datos SQLite con gestión automática de transacciones.
    
    Los métodos de dominio están organizados en mixins:
    - UsersMixin: gestión de usuarios
    - ItemsMixin: gestión de productos/inventario
    - SalesMixin: registro y consulta de ventas
    - MetricsMixin: métricas y reportes
    - PasswordResetMixin: recuperación de contraseña
    
    Attributes:
        db_path (str): Ruta al archivo de base de datos SQLite
    """

    def __init__(self, db_path):
        self.db_path = db_path

    def _connect(self):
        """
        Crea una conexión a la base de datos con configuración segura.
        
        Returns:
            sqlite3.Connection: Conexión activa con foreign keys habilitadas
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.execute("PRAGMA cache_size = -8000")
        except sqlite3.OperationalError as e:
            if "unable to open database file" in str(e).lower():
                logger.error(f"Database file not found at {self.db_path}: {e}", exc_info=True)
                raise DatabaseError(f"Database file not found at {self.db_path}")
        except sqlite3.Error as e:
            logger.error(f"Error connecting to database: {e}", exc_info=True)
            raise DatabaseError(f"Error connecting to database: {e}")
        return conn

    @contextlib.contextmanager
    def _cursor(self):
        """Context manager para ejecutar consultas con transacciones automáticas."""
        conn = self._connect()
        start = time.perf_counter()
        try:
            cur = conn.cursor()
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
            conn.close()
            logger.debug("[DB] Conexión cerrada")

    def init_db(self):
        """Inicializa la base de datos creando todas las tablas necesarias."""
        users_table_query = """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            email TEXT NOT NULL,
            role TEXT NOT NULL,
            status INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        items_table_query = """
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            barrs_code TEXT UNIQUE,
            description TEXT,
            name TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0,
            min_quantity INTEGER NOT NULL DEFAULT 5,
            price REAL NOT NULL,
            status INTEGER NOT NULL DEFAULT 1
        )
        """
        sells_details_table_query = """
        CREATE TABLE IF NOT EXISTS details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sell_id INTEGER NOT NULL,
            item_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            vendedor TEXT NOT NULL,
            payment_method TEXT NOT NULL DEFAULT 'Efectivo',
            FOREIGN KEY (sell_id) REFERENCES sells (id),
            FOREIGN KEY (item_id) REFERENCES items (id)
        )
        """
        sells_table_query = """
        CREATE TABLE IF NOT EXISTS sells (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            vendedor TEXT NOT NULL,
            payment_method TEXT NOT NULL DEFAULT 'Efectivo',
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
        
        with self._cursor() as cur:
            cur.execute(users_table_query)
            cur.execute(items_table_query)
            cur.execute(sells_table_query)
            cur.execute(sells_details_table_query)
            cur.execute(reset_codes_table_query)
            
            cur.execute(item_attributes_table_query)
            cur.execute(item_attribute_values_table_query)

        self._run_migrations()

    def _run_migrations(self):
        """Aplica migraciones incrementales (idempotentes)."""
        migrations = [
            ("sells", "vendedor", "TEXT NOT NULL DEFAULT 'unknown'"),
            ("sells", "payment_method", "TEXT NOT NULL DEFAULT 'Efectivo'"),
            ("details", "vendedor", "TEXT NOT NULL DEFAULT 'unknown'"),
            ("details", "payment_method", "TEXT NOT NULL DEFAULT 'Efectivo'"),
            ("users", "status", "INTEGER NOT NULL DEFAULT 1"),
            ("users", "created_at", "TEXT DEFAULT NULL"),
        ]
        conn = self._connect()
        try:
            cur = conn.cursor()
            for table, column, definition in migrations:
                try:
                    cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
                    logger.info(f"[Migration] Columna '{column}' agregada a '{table}'")
                except Exception:
                    pass
            conn.commit()
        finally:
            conn.close()

    def create_table(self, table_name, columns):
        """Crea una tabla personalizada (IF NOT EXISTS)."""
        cols_with_types = ", ".join(
            [f"{col} {dtype}" for col, dtype in columns.items()]
        )
        query = f"CREATE TABLE IF NOT EXISTS {table_name} ({cols_with_types})"
        with self._cursor() as cur:
            cur.execute(query)

    @measure_time
    def execute_query(self, query, params=(), fetch=True):
        """
        Ejecuta una consulta SQL arbitraria con parámetros seguros.

        Args:
            query (str): Consulta SQL con placeholders (?)
            params (tuple): Valores para los placeholders
            fetch (bool): Si True retorna resultados, si False retorna filas afectadas

        Returns:
            list[tuple] | int: Resultados o filas afectadas
        """
        with self._cursor() as cur:
            cur.execute(query, params)
            if fetch:
                logger.debug(f"Executed query: {query} with params: {params}")
                return cur.fetchall()
            logger.debug(f"Rows affected: {cur.rowcount} for query: {query} with params: {params}")
            return cur.rowcount