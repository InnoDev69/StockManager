from datetime import datetime
from tools.logger import logger
from tools.local_time import localDate

from bd.bdErrors import DatabaseError


class ItemsMixin:
    """Métodos de gestión de productos/inventario."""

    def add_item(self, barrs_code: str, description, name, quantity, min_quantity, expiration_date, price: float):
        """
        Agrega un nuevo producto al inventario.

        Args:
            barrs_code (str|None): Código de barras (puede ser None)
            description (str): Descripción del producto
            name (str): Nombre del producto
            quantity (int): Cantidad inicial en stock
            min_quantity (int): Stock mínimo antes de alerta
            expiration_date (str|None): Fecha de expiración (puede ser None)
            price (float): Precio de venta

        Raises:
            DatabaseError: Si el código de barras ya existe o hay error SQL

        Note:
            Si barrs_code es una cadena vacía, se convierte a None
        """
        barrs_code = str(barrs_code).strip() if barrs_code else None
        self.execute_query(
            "INSERT INTO items (barrs_code, description, name, quantity, min_quantity, expiration_date, price, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (barrs_code, description, name, quantity, min_quantity, expiration_date, price, localDate(), localDate()),
        )

    def get_item_details(self, item_id):
        """
        Obtiene los detalles completos de un producto por su ID.

        Args:
            item_id (int): ID del producto

        Returns:
            dict|None: Detalles del producto o None si no existe
        """
        rows = self.execute_query(
            "SELECT barrs_code, description, name, quantity, min_quantity, expiration_date, price, status FROM items WHERE id = ?",
            (item_id,),
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
            "status": row[6],
            "expiration_date": row[7],
        }

    def disable_item(self, item_id):
        """Deshabilita un producto (status = 0)."""
        self.execute_query(
            "UPDATE items SET status = 0 WHERE id = ?",
            (item_id,),
            fetch=False,
        )

    def enable_item(self, item_id):
        """Habilita un producto (status = 1)."""
        self.execute_query(
            "UPDATE items SET status = 1 WHERE id = ?",
            (item_id,),
            fetch=False,
        )

    def get_item_by_id(self, item_id):
        """
        Obtener detalles completos de un producto por ID.
        Convierte tipos de dato apropiadamente.
        """
        query = """
            SELECT id, barrs_code, name, description, quantity as stock, 
                min_quantity, price, status, expiration_date, created_at, updated_at
            FROM items WHERE id = ?
        """
        result = self.execute_query(query, (item_id,))
        
        if not result:
            logger.warning(f"Producto con ID {item_id} no encontrado.")
            return None
        
        row = result[0]
        
        product = {
            "id": row[0],
            "barrs_code": row[1],
            "name": row[2],
            "description": row[3],
            "stock": row[4],
            "min_stock": row[5],
            "price": row[6],
            "status": row[7],
            "expiration_date": row[8],
            "created_at": row[9],
            "updated_at": row[10],
        }
        
        try:
            product['price'] = float(product['price']) if product['price'] else 0.0
        except (ValueError, TypeError):
            product['price'] = 0.0
        
        product['stock'] = int(product['stock']) if product.get('stock') else 0
        
        return product
    
    def get_item_name(self, item_id):
        """Obtiene el nombre de un producto por su ID."""
        rows = self.execute_query(
            "SELECT name FROM items WHERE id = ?",
            (item_id,)
        )
        return rows[0][0] if rows else None
    
    def check_and_notify_low_stock(self, user_id):
        """
        Verifica el stock de todos los productos y crea una notificación si está bajo.
        Si el stock se recupera, resetea la notificación para futuras alertas.
        Args:
            user_id (int): ID del usuario a notificar
        """
        items = self.execute_query(
            """SELECT id, name, quantity, min_quantity, notified_low_stock
            FROM items
            WHERE status = 1
                AND quantity IS NOT NULL
                AND min_quantity IS NOT NULL"""
        )

        to_notify = []   # ids a marcar notified_low_stock = 1
        to_reset = []    # ids a marcar notified_low_stock = 0

        for item_id, name, quantity, min_quantity, notified in items:
            if quantity < min_quantity and not notified:
                self.create_notification(
                    user_id=user_id,
                    title="Stock bajo",
                    message=f"El producto {name} (ID: {item_id}) tiene stock bajo ({quantity} unidades).",
                    notification_type='warning'
                )
                to_notify.append(item_id)
            elif quantity >= min_quantity and notified:
                to_reset.append(item_id)

        if to_notify:
            placeholders = ",".join("?" * len(to_notify))
            self.execute_query(
                f"UPDATE items SET notified_low_stock = 1 WHERE id IN ({placeholders})",
                tuple(to_notify),
                fetch=False
            )

        if to_reset:
            placeholders = ",".join("?" * len(to_reset))
            self.execute_query(
                f"UPDATE items SET notified_low_stock = 0 WHERE id IN ({placeholders})",
                tuple(to_reset),
                fetch=False
            )
                    
    def activate_item(self, item_id):
        """Activa un producto deshabilitado."""
        self.execute_query(
            "UPDATE items SET status = 1 WHERE id = ?",
            (item_id,),
            fetch=False,
        )

    def update_item_barcode(self, item_id, new_barrs_code):
        """
        Actualiza el código de barras de un producto.
        
        Args:
            item_id: ID del producto
            new_barrs_code: Nuevo código de barras
            
        Raises:
            DatabaseError: Si hay duplicado o no existe
        """
        try:
            self.execute_query(
                "UPDATE items SET barrs_code = ?, updated_at = ? WHERE id = ?",
                (new_barrs_code, localDate(), item_id)
            )
        except Exception as e:
            raise DatabaseError(f"Error al actualizar código de barras: {e}")

    def generate_barcode_image(self, barrs_code):
        """
        Genera imagen PNG del código de barras.
        Detecta automáticamente el tipo o usa CODE128 por defecto.
        
        Args:
            barrs_code: El código a codificar
            
        Returns:
            BytesIO: Imagen PNG del código de barras
        """
        from io import BytesIO
        try:
            import barcode
        except ImportError:
            raise DatabaseError("Librería 'python-barcode' no instalada. Ejecuta: pip install python-barcode pillow")
        
        barcode_type = self._detect_barcode_type(barrs_code)
        
        try:
            BarcodeClass = barcode.get_barcode_class(barcode_type)
            bc = BarcodeClass(barrs_code, writer=barcode.writer.ImageWriter())
            
            img_io = BytesIO()
            bc.write(img_io, options={"write_text": False})
            img_io.seek(0)
            
            return img_io
        except Exception as e:
            raise DatabaseError(f"Error generando barcode ({barcode_type}): {str(e)}")

    def _detect_barcode_type(self, code):
        """
        Detecta el tipo de código de barras basado en el formato.
        
        Returns:
            str: Tipo de código ('code128', 'ean13', 'upca', etc.)
        """
        if not code:
            return 'code128'
        
        code = str(code).strip()
        length = len(code)
        
        # EAN-13 (13 dígitos)
        if length == 13 and code.isdigit():
            return 'ean13'
        
        # EAN-8 (8 dígitos)
        if length == 8 and code.isdigit():
            return 'ean8'
        
        # UPC-A (12 dígitos)
        if length == 12 and code.isdigit():
            return 'upca'
        
        # UPC-E (6 o 8 dígitos)
        if length in (6, 8) and code.isdigit():
            return 'upce'
        
        # ISBN-13 (con o sin guiones)
        if (length == 13 or length == 17) and (code.isdigit() or '-' in code):
            if code.startswith('978') or code.startswith('979'):
                return 'isbn13'
        
        # ISBN-10 (10 dígitos + X opcional)
        if length == 10 and (code[:-1].isdigit() and code[-1] in '0123456789X'):
            return 'isbn10'
        
        # Código personalizado (PRD######)
        if code.startswith('PRD'):
            return 'code128'
        
        # Por defecto es CODE128 (acepta más caracteres)
        return 'code128'
    
    def get_all_items(self):
        """Obtiene una lista de todos los productos activos."""
        rows = self.execute_query(
        "SELECT id, barrs_code, name, description, quantity, min_quantity, price, expiration_date FROM items WHERE status = 1 ORDER BY name ASC"
        )
        
        return [
            {
                "id": row[0],
                "barrs_code": row[1],
                "name": row[2],
                "description": row[3],
                "quantity": row[4],
                "min_quantity": row[5],
                "price": row[6],
                "expiration_date": row[7]
            }
            for row in rows
        ]