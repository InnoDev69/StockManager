import sqlite3
import contextlib
from bd.bdErrors import *

class BDConector:
    """
    Conector de base de datos SQLite con gestión automática de transacciones.
    
    Características:
    - Context managers para conexiones seguras
    - Commit/rollback automático
    - Foreign keys habilitadas por defecto
    - Manejo centralizado de errores
    
    Attributes:
        db_path (str): Ruta al archivo de base de datos SQLite
    """
    
    def __init__(self, db_path):
        """
        Inicializa el conector de base de datos.
        
        Args:
            db_path (str): Ruta al archivo SQLite (ej: './data/stock.db')
        
        Example:
            db = BDConector('./data/stock.db')
        """
        
        self.db_path = db_path

    def _connect(self):
        """
        Crea una conexión a la base de datos con configuración segura.
        
        Thread-safe: No (crear una instancia por thread).
        
        Returns:
            sqlite3.Connection: Conexión activa con foreign keys habilitadas
        
        Note:
            PRAGMA foreign_keys = ON asegura integridad referencial
        """
        
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @contextlib.contextmanager
    def _cursor(self):
        """
        Context manager para ejecutar consultas con transacciones automáticas.
        
        Thread-safe: No (crear una instancia por thread).
        Transaccional: Sí (auto commit/rollback).
        
        Yields:
            sqlite3.Cursor: Cursor activo para ejecutar consultas
        
        Raises:
            DatabaseError: Si ocurre un error SQL (con rollback automático)
        
        Example:
            with self._cursor() as cur:
                cur.execute("INSERT INTO items (...) VALUES (?)", (data,))
        
        Note:
            - Hace commit automático al salir del bloque
            - Hace rollback en caso de excepción
            - Cierra la conexión siempre
        """
        
        conn = self._connect()
        try:
            cur = conn.cursor()
            yield cur
            conn.commit()
        
        except sqlite3.Error as e:
            conn.rollback()
            raise DatabaseError(f"Database error: {e}")    
            
        finally:
            conn.close()
    
    def init_db(self):
        """
        Inicializa la base de datos creando todas las tablas necesarias.
        
        Thread-safe: Sí (con locking de SQLite).
        Transaccional: Sí.
        Idempotente: Sí (usa IF NOT EXISTS).
        
        Tablas creadas:
            - users: Usuarios del sistema con autenticación
            - items: Productos del inventario
            - sells: Registro de transacciones de venta
            - details: Detalles de productos vendidos por transacción
        
        Raises:
            DatabaseError: Si falla la creación de alguna tabla
        
        Example:
            db = BDConector('./data/stock.db')
            db.init_db()
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
        Crea una tabla personalizada en la base de datos.
        
        Thread-safe: Sí.
        Transaccional: Sí.
        Idempotente: Sí (usa IF NOT EXISTS).
        
        Args:
            table_name (str): Nombre de la tabla a crear
            columns (dict): {nombre_columna: tipo_dato_sql}
        
        Example:
            db.create_table('logs', {
                'id': 'INTEGER PRIMARY KEY',
                'message': 'TEXT',
                'timestamp': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
            })
        
        Warning:
            No valida nombres de tabla ni tipos SQL. Usar con precaución.
        """
        cols_with_types = ", ".join([f"{col} {dtype}" for col, dtype in columns.items()])
        query = f"CREATE TABLE IF NOT EXISTS {table_name} ({cols_with_types})"
        with self._cursor() as cur:
            cur.execute(query)
    
    def execute_query(self, query, params=(), fetch=True):
        """
        Ejecuta una consulta SQL arbitraria con parámetros seguros.
        
        Thread-safe: Sí.
        Transaccional: Sí.
        SQL Injection Safe: Sí (usa parámetros preparados).
        
        Args:
            query (str): Consulta SQL con placeholders (?)
            params (tuple): Valores para los placeholders
            fetch (bool): Si True retorna resultados, si False retorna filas afectadas
        
        Returns:
            list[tuple]: Resultados de la consulta si fetch=True
            int: Número de filas afectadas si fetch=False
        
        Raises:
            DatabaseError: Si la consulta falla
        
        Example:
            # Consulta SELECT
            rows = db.execute_query("SELECT * FROM items WHERE price > ?", (100,))
            
            # Consulta INSERT/UPDATE/DELETE
            affected = db.execute_query(
                "UPDATE items SET price = ? WHERE id = ?",
                (150.50, 1),
                fetch=False
            )
        
        Warning:
            Siempre usar placeholders (?) para prevenir SQL injection.
        """
        
        with self._cursor() as cur:
            cur.execute(query, params)
            if fetch:
                return cur.fetchall()
            return cur.rowcount
    
    def user_exists(self, username, email):
        """
        Verifica si un usuario ya existe por nombre o email.
        
        Thread-safe: Sí.
        Transaccional: No requiere (solo lectura).
        
        Args:
            username (str): Nombre de usuario a verificar
            email (str): Email a verificar
        
        Returns:
            bool: True si existe un usuario con ese username o email
        
        Example:
            if db.user_exists('admin', 'admin@example.com'):
                print("Usuario ya registrado")
        """
        
        rows = self.execute_query("SELECT id FROM users WHERE username = ? OR email = ?", (username, email))
        return len(rows) > 0
    
    def add_user(self, username, password, email, role="user"):
        """
        Registra un nuevo usuario en el sistema.
        
        Thread-safe: Sí.
        Transaccional: Sí.
        
        Args:
            username (str): Nombre de usuario único
            password (str): Contraseña hasheada (NO texto plano)
            email (str): Correo electrónico
            role (str): Rol del usuario ('admin' o 'user', default: 'user')
        
        Raises:
            DatabaseError: Si el usuario ya existe o hay un error SQL
        
        Example:
            from werkzeug.security import generate_password_hash
            hashed = generate_password_hash('mi_password')
            db.add_user('juan', hashed, 'juan@example.com', 'admin')
        
        Warning:
            NUNCA pasar contraseñas en texto plano. Hashear antes de llamar.
        """
        
        self.execute_query(
            "INSERT INTO users (username, password, email, role) VALUES (?, ?, ?, ?)",
            (username, password, email, role),
            fetch=False
        )
        
    def add_item(self, barrs_code, description, name, quantity, min_quantity, price):
        """
        Agrega un nuevo producto al inventario.
        
        Thread-safe: Sí.
        Transaccional: Sí.
        
        Args:
            barrs_code (str|None): Código de barras (puede ser None)
            description (str): Descripción del producto
            name (str): Nombre del producto
            quantity (int): Cantidad inicial en stock
            min_quantity (int): Stock mínimo antes de alerta
            price (float): Precio de venta
        
        Raises:
            DatabaseError: Si el código de barras ya existe o hay error SQL
        
        Example:
            db.add_item('7501234567890', 'Refresco 2L', 'Coca Cola', 50, 10, 25.50)
        
        Note:
            Si barrs_code es una cadena vacía, se convierte a None
        """
        
        barrs_code = barrs_code.strip() if barrs_code else None
        
        
        
        self.execute_query(
            "INSERT INTO items (barrs_code, description, name, quantity, min_quantity, price) VALUES (?, ?, ?, ?, ?, ?)",
            (barrs_code, description, name, quantity, min_quantity, price),
            fetch=False
        )
        
    def get_item_by_barcode(self, barcode):
        """
        Busca un producto por su código de barras.
        
        Thread-safe: Sí.
        Transaccional: No requiere (solo lectura).
        
        Args:
            barcode (str): Código de barras del producto
        
        Returns:
            tuple|None: (id, barrs_code, name, description, quantity, price) o None si no existe
        
        Example:
            item = db.get_item_by_barcode('7501234567890')
            if item:
                item_id, barcode, name, desc, stock, price = item
                print(f"{name}: ${price} ({stock} unidades)")
        """
        
        rows = self.execute_query(
            "SELECT id, barrs_code, name, description, quantity, price FROM items WHERE barrs_code = ?",
            (barcode,)
        )
        return rows[0] if rows else None
    
    def get_item_stock(self, item_id):
        """
        Obtiene la cantidad en stock de un producto.
        
        Thread-safe: Sí.
        Transaccional: No requiere (solo lectura).
        
        Args:
            item_id (int): ID del producto
        
        Returns:
            int|None: Cantidad en stock o None si el producto no existe
        
        Example:
            stock = db.get_item_stock(5)
            if stock is not None and stock < 10:
                print("Stock bajo!")
        """
        
        rows = self.execute_query(
            "SELECT quantity FROM items WHERE id = ?",
            (item_id,)
        )
        return rows[0][0] if rows else None

    def get_dashboard_stats(self):
        """
        Obtiene estadísticas agregadas para el dashboard principal.
        
        Thread-safe: Sí.
        Transaccional: No requiere (solo lecturas).
        
        Returns:
            dict: Estadísticas con las siguientes claves:
                - products (int): Total de productos en inventario
                - low_stock (int): Productos con stock <= min_quantity
                - sales_today (int): Ventas realizadas hoy
                - low_stock_list (list): Top 10 productos con stock crítico
                    - id (int): ID del producto
                    - name (str): Nombre del producto
                    - sku (str): Código de barras
                    - stock (int): Cantidad actual
        
        Example:
            stats = db.get_dashboard_stats()
            print(f"Total productos: {stats['products']}")
            print(f"Stock bajo: {stats['low_stock']}")
            for item in stats['low_stock_list']:
                print(f"  {item['name']}: {item['stock']} unidades")
        """
        
        total_products = self.execute_query("SELECT COUNT(*) FROM items")[0][0]
        
        low_stock = self.execute_query(
            "SELECT COUNT(*) FROM items WHERE quantity <= min_quantity AND quantity > 0"
        )[0][0]
        
        sales_today = self.execute_query(
            "SELECT COUNT(*) FROM sells WHERE DATE(date) = DATE('now')"
        )[0][0]
        
        low_stock_items = self.execute_query(
            "SELECT id, name, barrs_code, quantity FROM items WHERE quantity <= min_quantity ORDER BY quantity ASC LIMIT 10"
        )
        
        low_stock_list = [
            {
                "id": row[0],
                "name": row[1],
                "sku": row[2],
                "stock": row[3]
            }
            for row in low_stock_items
        ]
        
        return {
            "products": total_products,
            "low_stock": low_stock,
            "sales_today": sales_today,
            "low_stock_list": low_stock_list
        }

    def record_product_sale(self, item_id, quantity):
        """
        Registra una venta y actualiza el inventario de forma atómica.
        
        Thread-safe: Sí.
        Transaccional: Sí (rollback automático si falla).
        Atómica: Sí (inserta venta + detalles + actualiza stock en una transacción).
        
        Args:
            item_id (int): ID del producto a vender
            quantity (int): Cantidad a vender
        
        Raises:
            ValueError: Si no hay stock suficiente
            DatabaseError: Si el producto no existe o hay error SQL
        
        Example:
            try:
                db.record_product_sale(item_id=5, quantity=3)
                print("Venta registrada exitosamente")
            except ValueError as e:
                print(f"Error: {e}")
        
        Note:
            - Valida stock disponible antes de actualizar
            - Captura el precio actual del producto
            - Crea registro en 'sells' y 'details'
            - Actualiza stock en 'items'
            - Todo en una sola transacción (commit/rollback automático)
        """
        
        with self._cursor() as cur:
            cur.execute("INSERT INTO sells (item_id) VALUES (?)", (item_id,))
            sell_id = cur.lastrowid
            
            cur.execute("SELECT price, quantity FROM items WHERE id = ?", (item_id,))
            row = cur.fetchone()
            if not row:
                return
            price, current_qty = row
            if current_qty < quantity:
                raise ValueError("Stock insuficiente")

            cur.execute(
                "INSERT INTO details (sell_id, item_id, quantity, price) VALUES (?, ?, ?, ?)",
                (sell_id, item_id, quantity, price)
            )
            
            cur.execute(
                "UPDATE items SET quantity = ? WHERE id = ?",
                (current_qty - quantity, item_id)
            )