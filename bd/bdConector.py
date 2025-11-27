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
            barrs_code TEXT UNIQUE,  -- Ahora puede ser NULL
            description TEXT,
            name TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0,
            min_quantity INTEGER NOT NULL DEFAULT 5,
            price REAL NOT NULL
        )
        """
        
        sells_details_table_query = """
        CREATE TABLE IF NOT EXISTS details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sell_id INTEGER NOT NULL,
            item_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            FOREIGN KEY (sell_id) REFERENCES sells (id),
            FOREIGN KEY (item_id) REFERENCES items (id)
        )
        """
    
        sells_table_query = """
        CREATE TABLE IF NOT EXISTS sells (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (item_id) REFERENCES items (id)
        )
        """
        with self._cursor() as cur:
            cur.execute(users_table_query)  
            cur.execute(items_table_query)
            cur.execute(sells_table_query)
            cur.execute(sells_details_table_query)
    
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
        
    def add_item(self, barrs_code, description, name, quantity, min_quantity, price):
        # Permitir código de barras vacío
        barrs_code = barrs_code.strip() if barrs_code else None
        self.execute_query(
            "INSERT INTO items (barrs_code, description, name, quantity, min_quantity, price) VALUES (?, ?, ?, ?, ?, ?)",
            (barrs_code, description, name, quantity, min_quantity, price),
            fetch=False
        )
        
    def get_item_by_barcode(self, barcode):
        """
        Devuelve una tupla consistente:
        (id, barrs_code, name, description, quantity, price) o None
        """
        rows = self.execute_query(
            "SELECT id, barrs_code, name, description, quantity, price FROM items WHERE barrs_code = ?",
            (barcode,)
        )
        return rows[0] if rows else None
    
    def get_item_stock(self, item_id):
        """
        Devuelve la cantidad en stock de un ítem específico.
        """
        rows = self.execute_query(
            "SELECT quantity FROM items WHERE id = ?",
            (item_id,)
        )
        return rows[0][0] if rows else None

    def record_product_sale(self, item_id, quantity):
        """
        Inserta venta en sells e inserta los detalles en details y actualiza stock de forma segura.
        """
        with self._cursor() as cur:
            # crear venta y obtener sell_id
            cur.execute("INSERT INTO sells (item_id) VALUES (?)", (item_id,))
            sell_id = cur.lastrowid
            # obtener precio actual y stock
            cur.execute("SELECT price, quantity FROM items WHERE id = ?", (item_id,))
            row = cur.fetchone()
            if not row:
                return
            price, current_qty = row
            if current_qty < quantity:
                raise ValueError("Stock insuficiente")

            # registrar detalle
            cur.execute(
                "INSERT INTO details (sell_id, item_id, quantity, price) VALUES (?, ?, ?, ?)",
                (sell_id, item_id, quantity, price)
            )
            # actualizar stock
            cur.execute(
                "UPDATE items SET quantity = ? WHERE id = ?",
                (current_qty - quantity, item_id)
            )