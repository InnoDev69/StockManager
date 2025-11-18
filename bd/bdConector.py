import sqlite3
import contextlib

class BDConector:
    def __init__(self, db_path):
        self.db_path = db_path

    def _connect(self):
        return sqlite3.connect(self.db_path)

    @contextlib.contextmanager
    def _cursor(self):
        """
        Context manager que abre una conexión y cursor, hace commit al salir y cierra.
        Uso: with self._cursor() as cur: cur.execute(...)
        """
        conn = self._connect()
        try:
            cur = conn.cursor()
            yield cur
            conn.commit()
        finally:
            conn.close()
    
    def init_db(self):
        """
        Inicializa la base de datos creando las tablas necesarias.
        """
        users_table_query = """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            email TEXT NOT NULL,
            role TEXT NOT NULL
        )
        """
        items_table_query = """
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            barrs_code TEXT NOT NULL UNIQUE,
            description TEXT NOT NULL,
            name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            min_quantity INTEGER NOT NULL,
            price REAL NOT NULL
        )
        """
        
        movements_table_query = """
        CREATE TABLE IF NOT EXISTS movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            movement_type TEXT NOT NULL,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (item_id) REFERENCES items (id)
        )
        """
        
        sells_table_query = """
        CREATE TABLE IF NOT EXISTS sells (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (item_id) REFERENCES items (id)
        )
        """
        with self._cursor() as cur:
            cur.execute(users_table_query)
            cur.execute(items_table_query)
            cur.execute(movements_table_query)
            cur.execute(sells_table_query)
    
    def create_table(self, table_name, columns):
        """
        Crea una tabla en la base de datos si no existe.
        
        Parámetros:
        - table_name (str): Nombre de la tabla a crear.
        - columns (dict): Diccionario con los nombres de las columnas como claves y sus tipos de datos como valores.
        """
        cols_with_types = ", ".join([f"{col} {dtype}" for col, dtype in columns.items()])
        query = f"CREATE TABLE IF NOT EXISTS {table_name} ({cols_with_types})"
        with self._cursor() as cur:
            cur.execute(query)
    
    def execute_query(self, query, params=(), fetch=True):
        """
        Ejecuta una consulta SQL en la base de datos.
        
        Parámetros:
        - query (str): La consulta SQL a ejecutar.
        - params (tuple): Parámetros opcionales para la consulta SQL.
        - fetch (bool): si True devuelve cur.fetchall(), si False devuelve None.
        """
        with self._cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall() if fetch else None
    
    def user_exists(self, username, email):
        rows = self.execute_query("SELECT id FROM users WHERE username = ? OR email = ?", (username, email))
        return len(rows) > 0
    
    def verify_user(self, username, password):
        rows = self.execute_query("SELECT id FROM users WHERE username = ? AND password = ?", (username, password))
        return rows[0][0] if rows else None
    
    def add_user(self, username, password, email, role="user"):
        self.execute_query(
            "INSERT INTO users (username, password, email, role) VALUES (?, ?, ?, ?)",
            (username, password, email, role),
            fetch=False
        )