import sqlite3
import contextlib
from flask import jsonify
from bd.bdErrors import *
from tools.timmer import measure_time
from tools.logger import logger
from data.validators import ItemValidator, UserValidator, ValidationError

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
        
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")      # lecturas concurrentes sin bloqueo
            conn.execute("PRAGMA synchronous = NORMAL")     # más rápido, seguro para WAL
            conn.execute("PRAGMA cache_size = -8000")       # 8MB de cache (default ~2MB)
        
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
            logger.debug(
                f"Transacción completa | "
                f"Filas afectadas: {cur.rowcount} | "
                f"Último ID: {cur.lastrowid}"
            )
        
        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"Database error: {e}", exc_info=True)
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
            price REAL NOT NULL,
            status INTEGER NOT NULL DEFAULT 1  -- 1=active, 0=disabled
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
        
        reset_codes_table_query = """
        CREATE TABLE IF NOT EXISTS password_resets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            code TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        
        with self._cursor() as cur:
            
            cur.execute(users_table_query)  
            cur.execute(items_table_query)
            cur.execute(sells_table_query)
            cur.execute(sells_details_table_query)
            cur.execute(reset_codes_table_query)
    
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
    
    @measure_time
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
                logger.debug(f"Executed query: {query} with params: {params}")
                return cur.fetchall()
            logger.debug(f"Rows affected: {cur.rowcount} for query: {query} with params: {params}")
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
        
    def add_item(self, barrs_code:str, description, name, quantity, min_quantity, price:float):
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
        
        barrs_code = str(barrs_code).strip() if barrs_code else None
        
        self.execute_query(
            "INSERT INTO items (barrs_code, description, name, quantity, min_quantity, price) VALUES (?, ?, ?, ?, ?, ?)",
            (barrs_code, description, name, quantity, min_quantity, price)
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
    
    def total_items(self):
        """
        Obtiene el total de productos activos en el inventario.
        
        Thread-safe: Sí.
        Transaccional: No requiere (solo lectura).
        
        Returns:
            int: Total de productos registrados
        
        Example:
            total = db.total_items()
            print(f"Total productos en inventario: {total}")
        """
        
        rows = self.execute_query("SELECT COUNT(*) FROM items WHERE status = 1")
        return rows[0][0] if rows else 0

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
        
        with self._cursor() as cur:
            cur.execute("""
                SELECT
                    (SELECT COUNT(*) FROM items WHERE status = 1),
                    (SELECT COUNT(*) FROM items WHERE quantity <= min_quantity AND quantity > 0 AND status = 1),
                    (SELECT COUNT(*) FROM sells WHERE DATE(date) = DATE('now'))
            """)
            total, low, today = cur.fetchone()

            cur.execute(
                "SELECT id, name, barrs_code, quantity FROM items "
                "WHERE status = 1 AND quantity <= min_quantity ORDER BY quantity ASC LIMIT 10"
            )
            low_list = [{"id": r[0], "name": r[1], "sku": r[2], "stock": r[3]} for r in cur.fetchall()]

        return {"products": total, "low_stock": low, "sales_today": today, "low_stock_list": low_list}

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
    
    def record_bulk_sale(self, items):
        """
        Registra una venta con múltiples productos en una sola transacción.
        
        Thread-safe: Sí.
        Transaccional: Sí (rollback automático si falla).
        Atómica: Sí (inserta venta + todos los detalles + actualiza stock en una transacción).
        
        Args:
            items (list): Lista de diccionarios con:
                - item_id (int): ID del producto
                - quantity (int): Cantidad a vender
        
        Returns:
            int: ID de la venta creada
        
        Raises:
            ValueError: Si no hay stock suficiente para algún producto
            DatabaseError: Si algún producto no existe o hay error SQL
        
        Example:
            try:
                sale_id = db.record_bulk_sale([
                    {"item_id": 5, "quantity": 3},
                    {"item_id": 8, "quantity": 2}
                ])
                print(f"Venta #{sale_id} registrada exitosamente")
            except ValueError as e:
                print(f"Error: {e}")
        
        Note:
            - Valida stock disponible para todos los productos antes de procesar
            - Captura el precio actual de cada producto
            - Crea un solo registro en 'sells' con múltiples 'details'
            - Actualiza stock de todos los productos
            - Todo en una sola transacción (commit/rollback automático)
        """
        
        if not items:
            raise ValueError("La lista de items no puede estar vacía")
        
        with self._cursor() as cur:
            cur.execute("INSERT INTO sells (item_id) VALUES (?)", (items[0]["item_id"],))
            sell_id = cur.lastrowid
            
            for item in items:
                item_id = item["item_id"]
                quantity = item["quantity"]
                
                cur.execute("SELECT price, quantity FROM items WHERE id = ?", (item_id,))
                row = cur.fetchone()
                if not row:
                    raise DatabaseError(f"Producto con ID {item_id} no encontrado")
                
                price, current_qty = row
                if current_qty < quantity:
                    raise ValueError(f"Stock insuficiente para producto ID {item_id}")
                
                cur.execute(
                    "INSERT INTO details (sell_id, item_id, quantity, price) VALUES (?, ?, ?, ?)",
                    (sell_id, item_id, quantity, price)
                )
                
                cur.execute(
                    "UPDATE items SET quantity = ? WHERE id = ?",
                    (current_qty - quantity, item_id)
                )
            
            return sell_id
            
    def disable_item(self, item_id):
        """
        Deshabilita un producto estableciendo su cantidad a cero.
        
        Thread-safe: Sí.
        Transaccional: Sí.
        
        Args:
            item_id (int): ID del producto a deshabilitar
        
        Raises:
            DatabaseError: Si hay un error SQL
        
        Example:
            db.disable_item(10)
        """
        
        self.execute_query(
            "UPDATE items SET status = 0 WHERE id = ?",
            (item_id,),
            fetch=False
        )
        
    def enable_item(self, item_id):
        """
        Habilita un producto estableciendo su estado a activo.
        
        Thread-safe: Sí.    
        Transaccional: Sí.
        Args:
            item_id (int): ID del producto a habilitar
        Raises:
            DatabaseError: Si hay un error SQL
        """
        
        self.execute_query(
            "UPDATE items SET status = 1 WHERE id = ?",
            (item_id,),
            fetch=False
        )
        
    def get_item_status(self, item_id):
        """
        Obtiene el estado (habilitado/deshabilitado) de un producto.
        
        Thread-safe: Sí.    
        Transaccional: No requiere (solo lectura).
        Args:
            item_id (int): ID del producto
        Returns:
            int|None: 1 si está habilitado, 0 si deshabilitado, None si no existe
        Example:
            status = db.get_item_status(5)
            
            if status == 1:
                print("Producto habilitado")
            elif status == 0:
                print("Producto deshabilitado")
            else:
                print("Producto no existe")
        """
        
        rows = self.execute_query(
            "SELECT status FROM items WHERE id = ?",
            (item_id,)
        )
        return rows[0][0] if rows else None
    
    def get_item_details(self, item_id):
        """
        Obtiene los detalles completos de un producto por su ID.
        
        Thread-safe: Sí.
        Transaccional: No requiere (solo lectura).
        
        Args:
            item_id (int): ID del producto
        
        Returns:
            dict|None: Detalles del producto o None si no existe
                - id (int)
                - barrs_code (str|None)
                - description (str)
                - name (str)
                - quantity (int)
                - min_quantity (int)
                - price (float)
                - status (int)
                
        Example:
            details = db.get_item_details(5)
        
        """
        rows = self.execute_query(
            "SELECT barrs_code, description, name, quantity, min_quantity, price, status FROM items WHERE id = ?",
            (item_id,)
        )
        if not rows:
            return None
        
        row = rows[0]
        return {
            "barrs_code": row[0],
            "description": row[1],
            "name": row[2],
            "quantity": row[3],
            "min_quantity": row[4],
            "price": row[5],
            "status": row[6]
        }
    
    def get_metrics_data(self, start_date, end_date, prev_start_date, prev_end_date):
        """
        Obtiene todas las métricas del negocio en una sola conexión.
        
        Ejecuta ~8 queries reutilizando la misma conexión SQLite en vez de
        abrir/cerrar una por cada query (~10 conexiones → 1).
        
        Args:
            start_date (str): Fecha inicio periodo actual (YYYY-MM-DD)
            end_date (str): Fecha fin periodo actual (YYYY-MM-DD)
            prev_start_date (str): Fecha inicio periodo anterior (YYYY-MM-DD)
            prev_end_date (str): Fecha fin periodo anterior (YYYY-MM-DD)
        
        Returns:
            dict: Métricas completas del negocio
        """
        
        kpi_query = """
            SELECT 
                COALESCE(SUM(d.quantity * d.price), 0),
                COUNT(DISTINCT s.id),
                COALESCE(SUM(d.quantity), 0)
            FROM sells s
            JOIN details d ON s.id = d.sell_id
            WHERE DATE(s.date) BETWEEN ? AND ?
        """
        
        with self._cursor() as cur:
            # KPIs actuales
            cur.execute(kpi_query, (start_date, end_date))
            kpis = cur.fetchone()
            
            # KPIs anteriores
            cur.execute(kpi_query, (prev_start_date, prev_end_date))
            prev_kpis = cur.fetchone()
            
            # Ventas en el tiempo
            cur.execute("""
                SELECT DATE(s.date), COALESCE(SUM(d.quantity * d.price), 0), COUNT(DISTINCT s.id)
                FROM sells s JOIN details d ON s.id = d.sell_id
                WHERE DATE(s.date) BETWEEN ? AND ?
                GROUP BY DATE(s.date) ORDER BY 1 ASC
            """, (start_date, end_date))
            sales_over_time = cur.fetchall()
            
            # Top productos
            cur.execute("""
                SELECT i.id, i.name, i.barrs_code, SUM(d.quantity), SUM(d.quantity * d.price)
                FROM details d JOIN items i ON d.item_id = i.id JOIN sells s ON d.sell_id = s.id
                WHERE DATE(s.date) BETWEEN ? AND ?
                GROUP BY i.id, i.name, i.barrs_code ORDER BY 4 DESC LIMIT 10
            """, (start_date, end_date))
            top_products = cur.fetchall()
            
            # Ventas por día de la semana
            cur.execute("""
                SELECT CAST(strftime('%w', s.date) AS INTEGER), COUNT(DISTINCT s.id)
                FROM sells s WHERE DATE(s.date) BETWEEN ? AND ? GROUP BY 1
            """, (start_date, end_date))
            weekday_sales = cur.fetchall()
            
            # Ventas por hora
            cur.execute("""
                SELECT CAST(strftime('%H', s.date) AS INTEGER), COUNT(DISTINCT s.id)
                FROM sells s WHERE DATE(s.date) BETWEEN ? AND ? GROUP BY 1
            """, (start_date, end_date))
            hourly_sales = cur.fetchall()
            
            # Alertas combinadas en UNA sola query
            cur.execute("""
                SELECT
                    SUM(CASE WHEN quantity = 0 AND status = 1 THEN 1 ELSE 0 END),
                    SUM(CASE WHEN quantity > 0 AND quantity <= min_quantity AND status = 1 THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status = 1 AND id NOT IN (
                        SELECT DISTINCT d.item_id FROM details d
                        JOIN sells s ON d.sell_id = s.id
                        WHERE DATE(s.date) >= DATE('now', '-30 days')
                    ) THEN 1 ELSE 0 END)
                FROM items
            """)
            alerts = cur.fetchone()
            
            # Revenue del mejor día de la semana
            best_weekday_idx = None
            best_day_revenue = 0
            if weekday_sales:
                sales_by_wd = [0] * 7
                for row in weekday_sales:
                    sqlite_wd = int(row[0])
                    adjusted = (sqlite_wd - 1) if sqlite_wd > 0 else 6
                    sales_by_wd[adjusted] = int(row[1])
                
                max_idx = sales_by_wd.index(max(sales_by_wd))
                sqlite_day = (max_idx + 1) % 7
                
                cur.execute("""
                    SELECT COALESCE(SUM(d.quantity * d.price), 0)
                    FROM sells s JOIN details d ON s.id = d.sell_id
                    WHERE DATE(s.date) BETWEEN ? AND ?
                    AND CAST(strftime('%w', s.date) AS INTEGER) = ?
                """, (start_date, end_date, sqlite_day))
                best_day_revenue = cur.fetchone()[0]
                best_weekday_idx = max_idx
        
        return {
            "kpis": kpis,
            "prev_kpis": prev_kpis,
            "sales_over_time": sales_over_time,
            "top_products": top_products,
            "weekday_sales": weekday_sales,
            "hourly_sales": hourly_sales,
            "alerts": alerts,
            "best_day_revenue": float(best_day_revenue) if best_day_revenue else 0,
            "best_weekday_idx": best_weekday_idx,
        }

    def get_user_by_email(self, email):
        """
        Busca un usuario por su email.
        
        Thread-safe: Sí.
        Transaccional: No requiere (solo lectura).
        
        Args:
            email (str): Email del usuario
        
        Returns:
            tuple|None: (id, username, password_hash, role) o None si no existe
        
        Example:
            user = db.get_user_by_email('user@example.com')
            
        """
        rows = self.execute_query(
            "SELECT id, username, password, role FROM users WHERE email = ?",
            (email,)
        )
        return rows[0] if rows else None
    
    def save_reset_code(self, email, code):
        """
        Guarda un código de recuperación para un usuario.
        
        Thread-safe: Sí.
        Transaccional: Sí.
        
        Args:
            email (str): Email del usuario
            code (str): Código de recuperación a guardar
        
        Raises:
            DatabaseError: Si hay un error SQL
        
        Example:
            db.save_reset_code('user@example.com', '123456')
            
        """
        
        self.execute_query(
            "INSERT INTO password_resets (email, code, created_at) VALUES (?, ?, datetime('now'))",
            (email, code),
            fetch=False
        )
        
    def get_reset_code(self, email):
        """
        Obtiene el código de recuperación en base al email del usuario y su tiempo de creacion..
        
        Thread-safe: Sí.
        Transaccional: No requiere (solo lectura).
        
        Args:
            email (str): Email del usuario
        
        Returns:
            tuple|None: (code, created_at) o None si no existe
        
        Example:
            reset = db.get_reset_code('user@example.com')
            
        """
        
        rows = self.execute_query("SELECT code, created_at FROM password_resets WHERE email = ? ORDER BY created_at DESC LIMIT 1", (email,))
        return rows[0] if rows else (None, None)
    
    def delete_reset_code(self, email):
        """
        Elimina los códigos de recuperación asociados a un email.
        
        Thread-safe: Sí.
        Transaccional: Sí.
        
        Args:
            email (str): Email del usuario
        
        Raises:
            DatabaseError: Si hay un error SQL
        
        Example:
            db.delete_reset_code('user@example.com')
        """
        self.execute_query("DELETE FROM password_resets WHERE email = ?", (email,), fetch=False)
        
    def update_user_password(self, email, new_password):
        """
        Actualiza la contraseña de un usuario identificado por su email.
        
        Thread-safe: Sí.
        Transaccional: Sí.
        
        Args:
            email (str): Email del usuario
            new_password (str): Nueva contraseña hasheada
        
        Raises:
            DatabaseError: Si el usuario no existe o hay error SQL
        
        Example:
            from werkzeug.security import generate_password_hash
            hashed = generate_password_hash('nueva_password')
            db.update_user_password('user@example.com', hashed)
        """
        self.execute_query(
            "UPDATE users SET password = ? WHERE email = ?",
            (new_password, email),
            fetch=False
        )
        
    def verify_code(self, email, code):
        """
        Verifica si el código de recuperación es válido para un email dado.
        
        Thread-safe: Sí.
        Transaccional: No requiere (solo lectura).
        
        Args:
            email (str): Email del usuario
            code (str): Código de recuperación a verificar
        
        Returns:
            bool: True si el código es válido, False en caso contrario
        
        Example:
            is_valid = db.verify_code('user@example.com', '123456')
            
        """

        rows = self.execute_query(
            "SELECT 1 FROM password_resets WHERE email = ? AND code = ? AND created_at > datetime('now', '-15 minutes')",
            (email, code)
        )
        return bool(len(rows) > 0)
