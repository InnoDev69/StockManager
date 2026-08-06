from server.bd.bdErrors import DatabaseError
from miscellaneous import logger, localDate
from client.config import config

class SalesMixin:
    """Métodos de registro y consulta de ventas."""

    def get_dashboard_stats(self):
        today = localDate()

        with self._cursor() as cur:

            cur.execute("""
                SELECT
                    (SELECT COUNT(*)
                    FROM items
                    WHERE status = 1),

                    (SELECT COUNT(*)
                    FROM items
                    WHERE quantity <= min_quantity
                        AND quantity > 0
                        AND status = 1),

                    (SELECT COUNT(*)
                    FROM sells
                    WHERE DATE(date) = ?)
            """, (today,))

            products, low_stock, sales_today = cur.fetchone()

            cur.execute("""
                SELECT
                    id,
                    name,
                    barrs_code,
                    quantity
                FROM items
                WHERE status = 1
                AND quantity <= min_quantity
                ORDER BY quantity ASC
                LIMIT 10
            """)

            low_stock_list = [
                {
                    "id": row[0],
                    "name": row[1],
                    "sku": row[2],
                    "stock": row[3]
                }
                for row in cur
            ]

        return {
            "products": products,
            "low_stock": low_stock,
            "sales_today": sales_today,
            "low_stock_list": low_stock_list
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

    def record_bulk_sale(
        self,
        items,
        vendor_id,
        payment_method="Efectivo",
        customer_id=None,
        amount_paid=None,
        force_credit=False,
    ):
        """
        Registra una venta con múltiples productos en una sola transacción.

        Args:
            items (list): Lista de dicts con {item_id, quantity}
            vendor_id (int): ID del vendedor
            payment_method (str): 'Efectivo', 'Fiado' o 'Mixto'
            customer_id (int|None): Requerido si payment_method es 'Fiado' o 'Mixto'
            amount_paid (float|None): Monto abonado en el momento.
                - Efectivo: se ignora, se asume pago total.
                - Fiado: se asume 0 si no se especifica.
                - Mixto: obligatorio, debe ser menor al total.
            force_credit (bool): Si True, permite superar el límite de crédito
                del cliente (uso reservado a roles admin en el endpoint).

        Returns:
            int: ID de la venta creada

        Raises:
            ValueError: Si la lista está vacía, no hay stock suficiente,
                o los datos de fiado son inconsistentes.
            DatabaseError: Si algún producto no existe.
        """
        if not items:
            raise ValueError("La lista de items no puede estar vacía")

        if payment_method in ("Fiado", "Mixto") and not customer_id:
            raise ValueError(f"payment_method '{payment_method}' requiere customer_id")

        logger.debug(f"Registrando venta con {items} items para vendor_id={vendor_id}")

        with self.transaction() as cur:
            try:
                cur.execute(
                    "INSERT INTO sells (item_id, vendor_id, payment_method, date, customer_id, amount_paid) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (items[0]["item_id"], vendor_id, payment_method, localDate(), customer_id, amount_paid),
                )
                sell_id = cur.lastrowid
            except Exception as e:
                raise DatabaseError(f"Error al registrar venta: {e}")

            total = 0.0
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

                total += price * quantity

                cur.execute(
                    "INSERT INTO details (sell_id, item_id, quantity, price, vendor_id, payment_method) VALUES (?, ?, ?, ?, ?, ?)",
                    (sell_id, item_id, quantity, price, vendor_id, payment_method),
                )
                cur.execute(
                    "UPDATE items SET quantity = ? WHERE id = ?",
                    (current_qty - quantity, item_id),
                )

            # --- Lógica de fiado ---
            if payment_method == "Fiado":
                paid = 0.0
            elif payment_method == "Mixto":
                if amount_paid is None or amount_paid <= 0 or amount_paid >= total:
                    raise ValueError("Mixto requiere un amount_paid mayor a 0 y menor al total")
                paid = amount_paid
            else:  # Efectivo u otro método de contado
                paid = total

            cur.execute(
                "UPDATE sells SET amount_paid = ? WHERE id = ?",
                (paid, sell_id),
            )

            due = round(total - paid, 2)
            if due > 0:
                self.record_credit_sale(
                    cur,
                    customer_id=customer_id,
                    sell_id=sell_id,
                    amount_due=due,
                    user_id=vendor_id,
                    force=force_credit,
                )

            return sell_id
        
    def get_sale_by_id(self, sale_id):
        with self._cursor() as cur:
            cur.execute("""
                SELECT s.id, s.date, s.vendor_id, s.payment_method, u.username,
                    s.customer_id, s.amount_paid,
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
            total = sum(r[8] * r[9] for r in rows)  # quantity * price
            amount_paid = first[6] if first[6] is not None else total

            return {
                "id": first[0],
                "date": first[1],
                "vendor_id": first[2],
                "vendedor": self.get_username_by_id(first[2]) if self.get_username_by_id(first[2]) else "unknown",
                "payment_method": first[3],
                "customer_id": first[5],
                "amount_paid": amount_paid,
                "pending": round(total - amount_paid, 2),
                "items": [
                    {"item_id": r[7], "quantity": r[8], "price": r[9], "name": r[10]}
                    for r in rows
                ]
            }

    def update_sale(self, sale_id, items, vendor_id, payment_method, user_id=None):
        """
        Actualiza una venta existente:
        1. Restaura stock de productos antiguos
        2. Deduce stock de nuevos productos
        3. Actualiza details y sells
        4. Si la venta tiene cliente asociado (fiado/mixto) y
           RECALCULATE_CREDIT_ON_SALE_EDIT está en True, ajusta el
           pendiente de cuenta corriente con un movimiento ADJUSTMENT.
           Si está en False, el pendiente fiado original no se toca.
        """
        with self.transaction() as cur:
            cur.execute(
                "SELECT customer_id, amount_paid FROM sells WHERE id = ?",
                (sale_id,)
            )
            row = cur.fetchone()
            if not row:
                raise DatabaseError(f"Venta {sale_id} no encontrada")
            old_customer_id, old_amount_paid = row

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

            new_total = 0.0
            for item in items:
                item_id = item["item_id"]
                quantity = item["quantity"]

                cur.execute("SELECT price, quantity FROM items WHERE id = ?", (item_id,))
                r = cur.fetchone()
                if not r:
                    raise DatabaseError(f"Producto {item_id} no encontrado")

                price, current_qty = r
                if current_qty < quantity:
                    raise ValueError(f"Stock insuficiente para ID {item_id}")

                new_total += price * quantity

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

            if old_customer_id and config.get("RECALCULATE_CREDIT_ON_SALE_EDIT", False):
                cur.execute(
                    "SELECT COALESCE(SUM(amount), 0) FROM account_movements "
                    "WHERE sell_id = ? AND type = 'DEBT'",
                    (sale_id,)
                )
                old_due_recorded = cur.fetchone()[0] or 0.0

                old_paid = old_amount_paid if old_amount_paid is not None else new_total
                new_due = round(new_total - old_paid, 2)
                diff = round(new_due - old_due_recorded, 2)

                if diff != 0:
                    cur.execute(
                        """
                        INSERT INTO account_movements
                            (customer_id, sell_id, type, amount, user_id, note)
                        VALUES (?, ?, 'ADJUSTMENT', ?, ?, ?)
                        """,
                        (
                            old_customer_id,
                            sale_id,
                            diff,
                            user_id or vendor_id,
                            f"Ajuste automático por edición de venta #{sale_id}",
                        ),
                    )
            # Si RECALCULATE_CREDIT_ON_SALE_EDIT es False (default),
            # no se toca account_movements: el pendiente fiado original
            # queda fijo aunque los productos/precios hayan cambiado.