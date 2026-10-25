from typing import NamedTuple

from core.bd.bdErrors import (
    DatabaseError,
    InsufficientStockError,
    ItemNotFoundError,
    ProductUnavailableError,
)
from miscellaneous import logger, localDate, Limits
from core.config import config


class ResolvedLine(NamedTuple):
    """Línea de venta por unidad ya resuelta contra la base (ver _resolve_unit_line)."""
    name: str
    price: float
    current_qty: int
    track_stock: bool

class SalesMixin:
    """Métodos de registro y consulta de ventas."""

    def get_dashboard_stats(self):
        # localDate() devuelve fecha y hora; para comparar contra DATE(date)
        # hace falta solo la parte de la fecha (YYYY-MM-DD).
        today = str(localDate())[:10]
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
                        AND status = 1
                        AND track_stock = 1),
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
                AND track_stock = 1
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
            DatabaseError: Si el producto no existe, no hay stock suficiente
                o hay error SQL (cualquier error se envuelve en DatabaseError).

        Nota: delega en create_mixed_sale, así que respeta track_stock y
        allow_custom_price (un producto de precio libre no se puede vender por
        esta vía: no recibe precio) y deja 'amount_paid' igual al total.
        """
        try:
            self.create_mixed_sale(
                localDate(),
                vendor_id,
                unit_lines=[{"item_id": item_id, "quantity": quantity}],
                payment_method=payment_method,
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
        Se deja como envoltorio de create_mixed_sale por compatibilidad con
        quien todavía la llame (misma firma, misma regla de precio y stock).

        Registra una venta con múltiples productos en una sola transacción.
        """
        if not items:
            raise ValueError("La lista de items no puede estar vacía")

        return self.create_mixed_sale(
            localDate(),
            vendor_id,
            unit_lines=items,
            payment_method=payment_method,
            customer_id=customer_id,
            amount_paid=amount_paid,
            force_credit=force_credit,
        )

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
                SELECT d.item_id, d.quantity, d.price, i.name, i.allow_custom_price
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
                {"item_id": r[0], "quantity": r[1], "price": r[2], "name": r[3],
                 "allow_custom_price": bool(r[4])}
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
        1. Restaura stock de productos antiguos (solo los que controlan stock)
        2. Deduce stock de nuevos productos (solo los que controlan stock)
        3. Actualiza details y sells (en ventas al contado, también lo cobrado)
        4. Si la venta tiene cliente asociado (fiado/mixto) y
           RECALCULATE_CREDIT_ON_SALE_EDIT está en True, ajusta el
           pendiente de cuenta corriente con un movimiento ADJUSTMENT.
           Si está en False, el pendiente fiado original no se toca.

        Los productos con precio libre (allow_custom_price) necesitan que cada
        línea de 'items' traiga su 'price'; para el resto se usa el de la base.

        NOTA: por ahora solo maneja líneas por unidad ('items'/'details').
        Editar líneas por peso ('weight_items'/'weight_details') no está
        soportado todavía (ver checklist).
        """
        with self.transaction() as cur:
            # 1. Verificar que la venta existe en 'sells'
            cur.execute(
                "SELECT customer_id, amount_paid FROM sells WHERE id = ?",
                (sale_id,)
            )
            row = cur.fetchone()
            if not row:
                raise DatabaseError(f"Venta {sale_id} no encontrada")
            old_customer_id, old_amount_paid = row

            # 2. Restaurar stock SOLO de los productos antiguos que controlan stock (track_stock = 1)
            cur.execute("""
                SELECT d.item_id, d.quantity FROM details d
                JOIN items i ON i.id = d.item_id
                WHERE d.sell_id = ? AND i.track_stock = 1
            """, (sale_id,))
            old_items = cur.fetchall()

            for old_item_id, old_qty in old_items:
                cur.execute(
                    "UPDATE items SET quantity = quantity + ? WHERE id = ?",
                    (old_qty, old_item_id)
                )

            # 3. Borrar el detalle viejo
            cur.execute("DELETE FROM details WHERE sell_id = ?", (sale_id,))

            # 4. Insertar los nuevos productos. Precio y stock se resuelven con la
            #    misma regla que en una venta nueva (_resolve_unit_line).
            new_total = 0.0
            for item in items:
                item_id = item["item_id"]
                quantity = item["quantity"]

                line = self._resolve_unit_line(cur, item)
                price, track_stock = line.price, line.track_stock
                new_total += round(price * quantity, 2)

                cur.execute(
                    "INSERT INTO details (sell_id, item_id, quantity, price, vendor_id, payment_method) VALUES (?, ?, ?, ?, ?, ?)",
                    (sale_id, item_id, quantity, price, vendor_id, payment_method)
                )

                # Descontar stock solo si el producto lo controla
                if track_stock:
                    cur.execute(
                        "UPDATE items SET quantity = quantity - ? WHERE id = ?",
                        (quantity, item_id)
                    )

            # 5. Actualizar cabecera de la venta
            if old_customer_id is None and old_amount_paid is not None:
                # Venta al contado: lo cobrado acompaña al nuevo total
                cur.execute(
                    "UPDATE sells SET vendor_id = ?, payment_method = ?, amount_paid = ? WHERE id = ?",
                    (vendor_id, payment_method, round(new_total, 2), sale_id)
                )
            else:
                cur.execute(
                    "UPDATE sells SET vendor_id = ?, payment_method = ? WHERE id = ?",
                    (vendor_id, payment_method, sale_id)
                )

            # 6. Recalcular cuenta corriente si corresponde
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
        Crea una venta y devuelve solo su id (int).
        Es un atajo de create_sale_detailed: ver allí las reglas y los errores.
        """
        return self.create_sale_detailed(
            date,
            vendor_id,
            unit_lines=unit_lines,
            weight_lines=weight_lines,
            payment_method=payment_method,
            customer_id=customer_id,
            amount_paid=amount_paid,
            force_credit=force_credit,
        )["sale_id"]

    def create_sale_detailed(
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
        Es el único punto donde se crea una venta: todas las reglas de
        disponibilidad, precio y stock viven acá (y en _resolve_unit_line).

        El precio y el stock de cada línea se vuelven a leer de la DB
        dentro de esta transacción: 'price' que venga en unit_lines /
        weight_lines se ignora, para no confiar en un valor calculado
        fuera de la transacción (posible carrera con otra venta).
        Única excepción: los productos con precio libre (allow_custom_price),
        que exigen un 'price' mayor a 0 (y hasta Limits.ITEM_PRICE_MAX).

        Args:
            date (str)
            vendor_id (int)
            unit_lines (list[dict]): cada dict con item_id, quantity
                (y price, solo para productos con precio libre)
            weight_lines (list[dict]): cada dict con weight_item_id, weight
            payment_method (str): 'Efectivo', 'Fiado' o 'Mixto'
            customer_id (int|None): requerido si payment_method es Fiado/Mixto
            amount_paid (float|None): monto abonado (requerido si es Mixto)
            force_credit (bool): permite superar el límite de crédito

        Returns:
            dict: lo necesario para responder la venta sin volver a consultar:
                sale_id (int), total (float),
                items (list): item_id, name, quantity, unit_price, subtotal
                weight_items (list): weight_item_id, name, weight, subtotal

        Raises:
            ValueError: sin líneas, datos de fiado inconsistentes o precio libre inválido.
            ItemNotFoundError: un producto no existe (es ValueError).
            ProductUnavailableError: un producto está deshabilitado (es ValueError).
            InsufficientStockError: stock insuficiente (es ValueError); lleva
                product, requested y available.
            CreditLimitExceededError / InsufficientBalanceError: crédito.
            DatabaseError: venta 100% por peso (limitación legacy de 'sells.item_id').
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

            self._validate_products(cur, unit_lines, weight_lines)

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
            unit_results = []
            weight_results = []

            for line in unit_lines:
                item_id, quantity = line["item_id"], line["quantity"]
                resolved = self._resolve_unit_line(cur, line)
                subtotal = round(resolved.price * quantity, 2)
                total += subtotal

                cur.execute(
                    """
                    INSERT INTO details (sell_id, item_id, quantity, price, vendor_id, payment_method)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (sell_id, item_id, quantity, resolved.price, vendor_id, payment_method),
                )
                if resolved.track_stock:
                    cur.execute(
                        "UPDATE items SET quantity = ? WHERE id = ?",
                        (resolved.current_qty - quantity, item_id),
                    )
                unit_results.append({
                    "item_id": item_id,
                    "name": resolved.name,
                    "quantity": quantity,
                    "unit_price": resolved.price,
                    "subtotal": subtotal,
                })

            for line in weight_lines:
                weight_item_id = line["weight_item_id"]
                weight = line["weight"]

                cur.execute(
                    "SELECT name, price, weight, price_per_gram FROM weight_items WHERE id = ?",
                    (weight_item_id,),
                )
                row = cur.fetchone()
                if not row:
                    raise ItemNotFoundError(f"Producto (por peso) con ID {weight_item_id} no encontrado")

                name, unit_price, current_weight, price_per_gram = row
                if current_weight < weight:
                    raise InsufficientStockError(
                        f"Stock insuficiente para producto (por peso) ID {weight_item_id}",
                        product=name,
                        requested=weight,
                        available=current_weight,
                    )

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
                weight_results.append({
                    "weight_item_id": weight_item_id,
                    "name": name,
                    "weight": weight,
                    "subtotal": line_price,
                })

            total = round(total, 2)
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

            return {
                "sale_id": sell_id,
                "items": unit_results,
                "weight_items": weight_results,
                "total": total,
            }

    def _validate_products(self, cur, unit_lines, weight_lines):
        """
        Verifica, antes de registrar nada, que todos los productos de la venta
        existan y estén habilitados (status = 1).

        Raises:
            ItemNotFoundError: algún producto no existe.
            ProductUnavailableError: algún producto está deshabilitado; el mensaje
                los lista a todos.

        Solo se aplica al crear una venta: editar una venta vieja no debe fallar
        porque un producto que ya figuraba en ella se deshabilitó después.
        """
        unavailable = []
        for table, key, lines, not_found_msg in (
            ("items", "item_id", unit_lines, "Producto con ID {} no encontrado"),
            ("weight_items", "weight_item_id", weight_lines, "Producto (por peso) con ID {} no encontrado"),
        ):
            if not lines:
                continue
            ids = [line[key] for line in lines]
            placeholders = ",".join("?" * len(ids))
            cur.execute(f"SELECT id, name, status FROM {table} WHERE id IN ({placeholders})", tuple(ids))
            info = {row[0]: row for row in cur.fetchall()}
            for line in lines:
                row = info.get(line[key])
                if row is None:
                    raise ItemNotFoundError(not_found_msg.format(line[key]))
                if row[2] == 0 and row[1] not in unavailable:
                    unavailable.append(row[1])

        if unavailable:
            raise ProductUnavailableError(
                f"Los siguientes productos no están disponibles: {', '.join(unavailable)}"
            )

    def _resolve_unit_line(self, cur, line):
        """
        Resuelve una línea de venta por unidad leyendo el producto de la DB
        (debe llamarse dentro de la transacción de la venta).

        Reglas, compartidas por crear y editar ventas:
        - Precio: el de la base, salvo en productos con allow_custom_price,
          que exigen un 'price' entre 0 (exclusivo) y Limits.ITEM_PRICE_MAX.
        - Stock: solo se valida si el producto tiene track_stock = 1.

        Args:
            cur: cursor de la transacción en curso
            line (dict): item_id, quantity y, opcionalmente, price

        Returns:
            ResolvedLine: name, price, current_qty y track_stock (indica si el
                llamador debe descontar stock del producto).

        Raises:
            ItemNotFoundError: producto no encontrado.
            ValueError: precio libre ausente o fuera de rango.
            InsufficientStockError: stock insuficiente (solo si track_stock).
        """
        item_id, quantity = line["item_id"], line["quantity"]
        cur.execute(
            "SELECT name, price, quantity, track_stock, allow_custom_price FROM items WHERE id = ?",
            (item_id,),
        )
        row = cur.fetchone()
        if not row:
            raise ItemNotFoundError(f"Producto con ID {item_id} no encontrado")
        name, price, current_qty, track_stock, custom_price = row

        if custom_price:
            # Único caso donde se acepta el precio que viene de afuera
            price = line.get("price")
            if price is None or price <= 0 or price > Limits.ITEM_PRICE_MAX:
                raise ValueError(f"'{name}' requiere un precio entre 0 y {Limits.ITEM_PRICE_MAX}")

        if track_stock and current_qty < quantity:
            raise InsufficientStockError(
                f"Stock insuficiente para producto ID {item_id}",
                product=name,
                requested=quantity,
                available=current_qty,
            )

        return ResolvedLine(name, price, current_qty, bool(track_stock))

    @staticmethod
    def __resolve_paid_amount(payment_method, amount_paid, total):
        """
        Resuelve cuánto se considera abonado según el método de pago.
        Usado por create_mixed_sale, el único punto donde se crea una venta.
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
            SELECT COALESCE(SUM(line_total), 0) FROM (
                SELECT price * quantity AS line_total FROM details WHERE sell_id = ?
                UNION ALL
                SELECT price AS line_total FROM weight_details WHERE sell_id = ?
            )
        """
        return self.get_count(query, (sell_id, sell_id))