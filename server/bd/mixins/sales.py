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

        # NOTA: no contempla weight_items todavía (ver checklist).
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
        DEPRECATED para nuevo código: usar create_mixed_sale, que cubre el
        mismo caso (solo unit_lines) y además soporta weight_lines.
        Se deja intacta por compatibilidad con quien todavía la llame.

        Registra una venta con múltiples productos en una sola transacción.
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

            paid = self.__resolve_paid_amount(payment_method, amount_paid, total)

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
        """
        Obtiene una venta con todas sus líneas (unidad y peso) para edición.
        """
        with self._cursor() as cur:
            cur.execute("""
                SELECT s.id, s.date, s.vendor_id, s.payment_method, u.username,
                    s.customer_id, s.amount_paid
                FROM sells s
                LEFT JOIN users u ON s.vendor_id = u.id
                WHERE s.id = ?
            """, (sale_id,))
            header = cur.fetchone()

            if not header:
                return None

            cur.execute("""
                SELECT d.item_id, d.quantity, d.price, i.name
                FROM details d
                JOIN items i ON d.item_id = i.id
                WHERE d.sell_id = ?
            """, (sale_id,))
            unit_rows = cur.fetchall()

            cur.execute("""
                SELECT wd.weight_item_id, wd.weight, wd.price, wi.name
                FROM weight_details wd
                JOIN weight_items wi ON wd.weight_item_id = wi.id
                WHERE wd.sell_id = ?
            """, (sale_id,))
            weight_rows = cur.fetchall()

        total = sum(r[1] * r[2] for r in unit_rows) + sum(r[2] for r in weight_rows)
        amount_paid = header[6] if header[6] is not None else total

        return {
            "id": header[0],
            "date": header[1],
            "vendor_id": header[2],
            "vendedor": header[4] or "unknown",
            "payment_method": header[3],
            "customer_id": header[5],
            "amount_paid": amount_paid,
            "pending": round(total - amount_paid, 2),
            "items": [
                {"item_id": r[0], "quantity": r[1], "price": r[2], "name": r[3]}
                for r in unit_rows
            ],
            "weight_items": [
                {"weight_item_id": r[0], "weight": r[1], "price": r[2], "name": r[3]}
                for r in weight_rows
            ],
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

        NOTA: por ahora solo maneja líneas por unidad ('items'/'details').
        Editar líneas por peso ('weight_items'/'weight_details') no está
        soportado todavía (ver checklist).
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

            if old_customer_id and config.get("features.RECALCULATE_CREDIT_ON_SALE_EDIT", default=False):
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

    # ------------------------------------------------------------------
    # Venta combinada: items normales + items por peso, con fiado/mixto
    # ------------------------------------------------------------------
    def create_mixed_sale(
        self,
        date,
        vendor_id,
        unit_lines=None,
        weight_lines=None,
        payment_method="Efectivo",
        customer_id=None,
        amount_paid=None,
        force_credit=False,
    ):
        """
        Crea una venta que puede combinar líneas por unidad y por peso,
        todo en una sola transacción atómica, con soporte de fiado/mixto.

        El precio y el stock de cada línea se vuelven a leer de la DB
        dentro de esta transacción: 'price' que venga en unit_lines /
        weight_lines se ignora, para no confiar en un valor calculado
        fuera de la transacción (posible carrera con otra venta).

        Args:
            date (str)
            vendor_id (int)
            unit_lines (list[dict]): cada dict con item_id, quantity
            weight_lines (list[dict]): cada dict con weight_item_id, weight
            payment_method (str): 'Efectivo', 'Fiado' o 'Mixto'
            customer_id (int|None): requerido si payment_method es Fiado/Mixto
            amount_paid (float|None): monto abonado (ver record_bulk_sale)
            force_credit (bool): permite superar el límite de crédito

        Returns:
            int: id de la venta creada

        Raises:
            ValueError: sin líneas, stock insuficiente, o datos de fiado
                inconsistentes.
            DatabaseError: producto no encontrado, o venta 100% por peso
                (limitación legacy de 'sells.item_id', ver nota abajo).
        """
        unit_lines = unit_lines or []
        weight_lines = weight_lines or []

        if not unit_lines and not weight_lines:
            raise ValueError("La venta necesita al menos una línea (unit_lines o weight_lines)")

        if payment_method in ("Fiado", "Mixto") and not customer_id:
            raise ValueError(f"payment_method '{payment_method}' requiere customer_id")

        logger.debug(
            f"Registrando venta mixta: {len(unit_lines)} unit_lines, "
            f"{len(weight_lines)} weight_lines, vendor_id={vendor_id}"
        )

        with self.transaction() as cur:
            if unit_lines:
                head_item_id = unit_lines[0]["item_id"]
            else:
                # 'sells.item_id' es NOT NULL en el esquema legacy: una
                # venta 100% por peso no tiene forma de cumplir esa
                # restricción hoy. Requiere migración (ver checklist:
                # "sells.item_id nullable"). Falla explícito en vez de
                # dejar que SQLite tire un IntegrityError críptico.
                raise DatabaseError(
                    "No se puede registrar una venta sin ningún producto por unidad: "
                    "'sells.item_id' todavía es NOT NULL en este esquema. "
                    "Aplicar la migración de 'sells.item_id nullable' primero."
                )

            try:
                cur.execute(
                    """
                    INSERT INTO sells (item_id, date, vendor_id, payment_method, customer_id, amount_paid)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (head_item_id, date, vendor_id, payment_method, customer_id, amount_paid),
                )
                sell_id = cur.lastrowid
            except Exception as e:
                raise DatabaseError(f"Error al registrar venta: {e}")

            total = 0.0

            for line in unit_lines:
                item_id = line["item_id"]
                quantity = line["quantity"]

                cur.execute("SELECT price, quantity FROM items WHERE id = ?", (item_id,))
                row = cur.fetchone()
                if not row:
                    raise DatabaseError(f"Producto con ID {item_id} no encontrado")

                price, current_qty = row
                if current_qty < quantity:
                    raise ValueError(f"Stock insuficiente para producto ID {item_id}")

                total += price * quantity

                cur.execute(
                    """
                    INSERT INTO details (sell_id, item_id, quantity, price, vendor_id, payment_method)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (sell_id, item_id, quantity, price, vendor_id, payment_method),
                )
                cur.execute(
                    "UPDATE items SET quantity = ? WHERE id = ?",
                    (current_qty - quantity, item_id),
                )

            for line in weight_lines:
                weight_item_id = line["weight_item_id"]
                weight = line["weight"]

                cur.execute(
                    "SELECT price, weight, price_per_gram FROM weight_items WHERE id = ?",
                    (weight_item_id,),
                )
                row = cur.fetchone()
                if not row:
                    raise DatabaseError(f"Producto (por peso) con ID {weight_item_id} no encontrado")

                unit_price, current_weight, price_per_gram = row
                if current_weight < weight:
                    raise ValueError(f"Stock insuficiente para producto (por peso) ID {weight_item_id}")

                line_price = round((weight / price_per_gram) * unit_price, 2)
                total += line_price

                cur.execute(
                    """
                    INSERT INTO weight_details
                        (sell_id, weight_item_id, weight, price, vendor_id, payment_method)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (sell_id, weight_item_id, weight, line_price, vendor_id, payment_method),
                )
                cur.execute(
                    "UPDATE weight_items SET weight = ? WHERE id = ?",
                    (current_weight - weight, weight_item_id),
                )

            paid = self.__resolve_paid_amount(payment_method, amount_paid, total)

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

    @staticmethod
    def __resolve_paid_amount(payment_method, amount_paid, total):
        """
        Resuelve cuánto se considera abonado según el método de pago.
        Compartido entre record_bulk_sale y create_mixed_sale para no
        duplicar (y desincronizar) esta lógica.
        """
        if payment_method == "Fiado":
            return 0.0
        elif payment_method == "Mixto":
            if amount_paid is None or amount_paid <= 0 or amount_paid >= total:
                raise ValueError("Mixto requiere un amount_paid mayor a 0 y menor al total")
            return amount_paid
        else:  # Efectivo u otro método de contado
            return total

    # ------------------------------------------------------------------
    # Lectura combinada: todas las líneas de una venta, normalizadas
    # ------------------------------------------------------------------
    def get_sale_lines(self, sell_id):
        """
        Devuelve todas las líneas de una venta (por unidad y por peso)
        en un formato unificado, listo para armar un ticket o reporte.

        Returns:
            list[tuple]: (sell_id, product_name, sale_type, amount, price)
                sale_type: 'unit' | 'weight'
                amount: cantidad (unidades) o gramos, según sale_type
        """
        query = """
            SELECT
                d.sell_id,
                i.name AS product_name,
                'unit' AS sale_type,
                d.quantity AS amount,
                d.price AS price
            FROM details d
            JOIN items i ON i.id = d.item_id
            WHERE d.sell_id = ?

            UNION ALL

            SELECT
                wd.sell_id,
                wi.name AS product_name,
                'weight' AS sale_type,
                wd.weight AS amount,
                wd.price AS price
            FROM weight_details wd
            JOIN weight_items wi ON wi.id = wd.weight_item_id
            WHERE wd.sell_id = ?
        """
        return self.execute_query(query, (sell_id, sell_id))

    # ------------------------------------------------------------------
    # Total de una venta, sumando ambas tablas
    # ------------------------------------------------------------------
    def get_sale_total(self, sell_id):
        """Suma el total de una venta contemplando líneas por unidad y por peso."""
        query = """
            SELECT COALESCE(SUM(price), 0) FROM (
                SELECT price FROM details WHERE sell_id = ?
                UNION ALL
                SELECT price FROM weight_details WHERE sell_id = ?
            )
        """
        return self.get_count(query, (sell_id, sell_id))