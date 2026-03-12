from bd.bdErrors import DatabaseError


class SalesMixin:
    """Métodos de registro y consulta de ventas."""

    def get_dashboard_stats(self):
        """
        Obtiene estadísticas agregadas para el dashboard principal.

        Returns:
            dict: {products, low_stock, sales_today, low_stock_list}
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
            low_list = [
                {"id": r[0], "name": r[1], "sku": r[2], "stock": r[3]}
                for r in cur.fetchall()
            ]

        return {
            "products": total,
            "low_stock": low,
            "sales_today": today,
            "low_stock_list": low_list,
        }

    def record_product_sale(self, item_id, quantity, vendedor, payment_method="Efectivo"):
        """
        Registra una venta y actualiza el inventario de forma atómica.

        Args:
            item_id (int): ID del producto a vender
            quantity (int): Cantidad a vender
            vendedor (str): Nombre del vendedor
            payment_method (str): Método de pago

        Raises:
            ValueError: Si no hay stock suficiente
            DatabaseError: Si el producto no existe o hay error SQL
        """
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO sells (item_id, vendedor, payment_method) VALUES (?, ?, ?)",
                (item_id, vendedor, payment_method),
            )
            sell_id = cur.lastrowid

            cur.execute("SELECT price, quantity FROM items WHERE id = ?", (item_id,))
            row = cur.fetchone()
            if not row:
                return
            price, current_qty = row
            if current_qty < quantity:
                raise ValueError("Stock insuficiente")

            cur.execute(
                "INSERT INTO details (sell_id, item_id, quantity, price, vendedor, payment_method) VALUES (?, ?, ?, ?, ?, ?)",
                (sell_id, item_id, quantity, price, vendedor, payment_method),
            )
            cur.execute(
                "UPDATE items SET quantity = ? WHERE id = ?",
                (current_qty - quantity, item_id),
            )

    def record_bulk_sale(self, items, vendedor, payment_method="Efectivo"):
        """
        Registra una venta con múltiples productos en una sola transacción.

        Args:
            items (list): Lista de dicts con {item_id, quantity}
            vendedor (str): Nombre del vendedor
            payment_method (str): Método de pago

        Returns:
            int: ID de la venta creada

        Raises:
            ValueError: Si la lista está vacía o no hay stock suficiente
            DatabaseError: Si algún producto no existe
        """
        if not items:
            raise ValueError("La lista de items no puede estar vacía")

        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO sells (item_id, vendedor, payment_method) VALUES (?, ?, ?)",
                (items[0]["item_id"], vendedor, payment_method),
            )
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
                    "INSERT INTO details (sell_id, item_id, quantity, price, vendedor, payment_method) VALUES (?, ?, ?, ?, ?, ?)",
                    (sell_id, item_id, quantity, price, vendedor, payment_method),
                )
                cur.execute(
                    "UPDATE items SET quantity = ? WHERE id = ?",
                    (current_qty - quantity, item_id),
                )

            return sell_id