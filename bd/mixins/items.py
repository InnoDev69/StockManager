from bd.bdErrors import DatabaseError


class ItemsMixin:
    """Métodos de gestión de productos/inventario."""

    def add_item(self, barrs_code: str, description, name, quantity, min_quantity, price: float):
        """
        Agrega un nuevo producto al inventario.

        Args:
            barrs_code (str|None): Código de barras (puede ser None)
            description (str): Descripción del producto
            name (str): Nombre del producto
            quantity (int): Cantidad inicial en stock
            min_quantity (int): Stock mínimo antes de alerta
            price (float): Precio de venta

        Raises:
            DatabaseError: Si el código de barras ya existe o hay error SQL

        Note:
            Si barrs_code es una cadena vacía, se convierte a None
        """
        barrs_code = str(barrs_code).strip() if barrs_code else None
        self.execute_query(
            "INSERT INTO items (barrs_code, description, name, quantity, min_quantity, price) VALUES (?, ?, ?, ?, ?, ?)",
            (barrs_code, description, name, quantity, min_quantity, price),
        )

    def get_item_by_barcode(self, barcode):
        """
        Busca un producto por su código de barras.

        Args:
            barcode (str): Código de barras del producto

        Returns:
            tuple|None: (id, barrs_code, name, description, quantity, price) o None
        """
        rows = self.execute_query(
            "SELECT id, barrs_code, name, description, quantity, price FROM items WHERE barrs_code = ?",
            (barcode,),
        )
        return rows[0] if rows else None

    def get_item_stock(self, item_id):
        """
        Obtiene la cantidad en stock de un producto.

        Args:
            item_id (int): ID del producto

        Returns:
            int|None: Cantidad en stock o None si el producto no existe
        """
        rows = self.execute_query(
            "SELECT quantity FROM items WHERE id = ?",
            (item_id,),
        )
        return rows[0][0] if rows else None

    def total_items(self):
        """
        Obtiene el total de productos activos en el inventario.

        Returns:
            int: Total de productos registrados
        """
        rows = self.execute_query("SELECT COUNT(*) FROM items WHERE status = 1")
        return rows[0][0] if rows else 0

    def get_item_details(self, item_id):
        """
        Obtiene los detalles completos de un producto por su ID.

        Args:
            item_id (int): ID del producto

        Returns:
            dict|None: Detalles del producto o None si no existe
        """
        rows = self.execute_query(
            "SELECT barrs_code, description, name, quantity, min_quantity, price, status FROM items WHERE id = ?",
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
        }

    def get_item_status(self, item_id):
        """
        Obtiene el estado (habilitado/deshabilitado) de un producto.

        Args:
            item_id (int): ID del producto

        Returns:
            int|None: 1 si habilitado, 0 si deshabilitado, None si no existe
        """
        rows = self.execute_query(
            "SELECT status FROM items WHERE id = ?",
            (item_id,),
        )
        return rows[0][0] if rows else None

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