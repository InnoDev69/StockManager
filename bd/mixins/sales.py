from bd.bdErrors import DatabaseError
from tools.local_time import localDate
from tools.logger import logger

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
                    (SELECT COUNT(*) FROM sells WHERE DATE(date) = ?)
            """, (localDate(),))
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

    def record_product_sale(self, item_id, quantity, vendor_id, payment_method="Efectivo"):
        """
        Registra una venta y actualiza el inventario de forma atómica.

        Args:
            item_id (int): ID del producto a vender
            quantity (int): Cantidad a vender
            vendor_id (int): ID del vendedor
            payment_method (str): Método de pago

        Raises:
            ValueError: Si no hay stock suficiente
            DatabaseError: Si el producto no existe o hay error SQL
        """
        with self._cursor() as cur:
            try:
                cur.execute(
                    "INSERT INTO sells (item_id, date,vendor_id, payment_method) VALUES (?, ?,?, ?)",
                    (item_id, localDate(), vendor_id, payment_method),
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
                    "INSERT INTO details (sell_id, item_id, quantity, price, vendor_id, payment_method) VALUES (?, ?, ?, ?, ?, ?)",
                    (sell_id, item_id, quantity, price, vendor_id, payment_method),
                )
                cur.execute(
                    "UPDATE items SET quantity = ? WHERE id = ?",
                    (current_qty - quantity, item_id),
                )
            except Exception as e:
                raise DatabaseError(f"Error al registrar venta: {e}")

    def record_bulk_sale(self, items, vendor_id, payment_method="Efectivo"):
        """
        Registra una venta con múltiples productos en una sola transacción.

        Args:
            items (list): Lista de dicts con {item_id, quantity}
            vendor_id (int): ID del vendedor
            payment_method (str): Método de pago

        Returns:
            int: ID de la venta creada

        Raises:
            ValueError: Si la lista está vacía o no hay stock suficiente
            DatabaseError: Si algún producto no existe
        """
        if not items:
            raise ValueError("La lista de items no puede estar vacía")

        logger.debug(f"Registrando venta con {items} items para vendor_id={vendor_id}")
        
        with self.transaction() as cur:
            try:
                cur.execute(
                    "INSERT INTO sells (item_id, vendor_id, payment_method, date) VALUES (?, ?, ?, ?)",
                    (items[0]["item_id"], vendor_id, payment_method, localDate()),
                )
                sell_id = cur.lastrowid
            except Exception as e:
                raise DatabaseError(f"Error al registrar venta: {e}")

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
                    "INSERT INTO details (sell_id, item_id, quantity, price, vendor_id, payment_method) VALUES (?, ?, ?, ?, ?, ?)",
                    (sell_id, item_id, quantity, price, vendor_id, payment_method),
                )
                cur.execute(
                    "UPDATE items SET quantity = ? WHERE id = ?",
                    (current_qty - quantity, item_id),
                )

            return sell_id
        
    def get_sale_by_id(self, sale_id):
        """Obtiene detalles completos de una venta por ID"""
        with self._cursor() as cur:
            cur.execute("""
                SELECT s.id, s.date, s.vendor_id, s.payment_method, u.username,
                    d.item_id, d.quantity, d.price, i.name
                FROM sells s
                JOIN details d ON s.id = d.sell_id
                JOIN items i ON d.item_id = i.id
                LEFT JOIN users u ON s.vendor_id = u.id
                WHERE s.id = ?
            """, (sale_id,))
            rows = cur.fetchall()
            
            if not rows:
                return None
            
            first = rows[0]
            return {
                "id": first[0],
                "date": first[1],
                "vendor_id": first[2],
                "vendedor": self.get_username_by_id(first[2]) if self.get_username_by_id(first[2]) else "unknown",
                "payment_method": first[3],
                "items": [
                    {"item_id": r[5], "quantity": r[6], "price": r[7], "name": r[8]}
                    for r in rows
                ]
            }

    def update_sale(self, sale_id, items, vendor_id, payment_method):
        """
        Actualiza una venta existente:
        1. Restaura stock de productos antiguos
        2. Deduce stock de nuevos productos
        3. Actualiza details y sells
        """
        with self.transaction() as cur:
            cur.execute("""
                SELECT item_id, quantity FROM details WHERE sell_id = ?
            """, (sale_id,))
            old_items = cur.fetchall()
            
            for old_item_id, old_qty in old_items:
                cur.execute(
                    "UPDATE items SET quantity = quantity + ? WHERE id = ?",
                    (old_qty, old_item_id)
                )
            
            cur.execute("DELETE FROM details WHERE sell_id = ?", (sale_id,))
            
            for item in items:
                item_id = item["item_id"]
                quantity = item["quantity"]
                
                cur.execute("SELECT price, quantity FROM items WHERE id = ?", (item_id,))
                row = cur.fetchone()
                if not row:
                    raise DatabaseError(f"Producto {item_id} no encontrado")
                
                price, current_qty = row
                if current_qty < quantity:
                    raise ValueError(f"Stock insuficiente para ID {item_id}")
                
                cur.execute(
                    "INSERT INTO details (sell_id, item_id, quantity, price, vendor_id, payment_method) VALUES (?, ?, ?, ?, ?, ?)",
                    (sale_id, item_id, quantity, price, vendor_id, payment_method)
                )
                cur.execute(
                    "UPDATE items SET quantity = quantity - ? WHERE id = ?",
                    (quantity, item_id)
                )
            
            cur.execute(
                "UPDATE sells SET vendor_id = ?, payment_method = ? WHERE id = ?",
                (vendor_id, payment_method, sale_id)
            )