from server.bd.bdErrors import DatabaseError, InsufficientBalanceError, CreditLimitExceededError
from miscellaneous import logger


class CreditMixin:
    """
    Gestión de clientes y cuenta corriente (fiado).

    El saldo nunca se guarda directo: se deriva siempre de la suma de
    movimientos en account_movements (DEBT resta al negocio / suma a la
    deuda del cliente, PAYMENT reduce la deuda, ADJUSTMENT es libre).
    """

    # ---------- Clientes ----------

    def create_customer(self, name, phone=None, credit_limit=None):
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO customers (name, phone, credit_limit) VALUES (?, ?, ?)",
                (name, phone, credit_limit),
            )
            return cur.lastrowid

    def get_customer(self, customer_id):
        return self.get_single_row(
            "SELECT id, name, phone, credit_limit, status FROM customers WHERE id = ?",
            (customer_id,),
        )

    def list_customers(self, search=None):
        if search:
            return self.get_all_rows(
                "SELECT id, name, phone, credit_limit, status FROM customers "
                "WHERE status = 1 AND name LIKE ? ORDER BY name",
                (f"%{search}%",),
            )
        return self.get_all_rows(
            "SELECT id, name, phone, credit_limit, status FROM customers "
            "WHERE status = 1 ORDER BY name"
        )

    # ---------- Saldo ----------

    def get_customer_balance(self, customer_id, cur=None):
        """
        Retorna el saldo pendiente del cliente (positivo = debe).
        """
        if cur is not None:
            cur.execute(
                """
                SELECT COALESCE(SUM(
                    CASE
                        WHEN type = 'DEBT' THEN amount
                        WHEN type = 'PAYMENT' THEN -amount
                        WHEN type = 'ADJUSTMENT' THEN amount
                    END
                ), 0)
                FROM account_movements
                WHERE customer_id = ?
                """,
                (customer_id,),
            )
            row = cur.fetchone()
        else:
            row = self.get_single_row(
                """
                SELECT COALESCE(SUM(
                    CASE
                        WHEN type = 'DEBT' THEN amount
                        WHEN type = 'PAYMENT' THEN -amount
                        WHEN type = 'ADJUSTMENT' THEN amount
                    END
                ), 0)
                FROM account_movements
                WHERE customer_id = ?
                """,
                (customer_id,),
            )
        return row[0] if row else 0.0

    def get_customer_movements(self, customer_id, limit=50):
        return self.get_all_rows(
            """
            SELECT id, sell_id, type, amount, date, user_id, note
            FROM account_movements
            WHERE customer_id = ?
            ORDER BY date DESC
            LIMIT ?
            """,
            (customer_id, limit),
        )

    # ---------- Movimientos ----------

    def record_credit_sale(self, cur, customer_id, sell_id, amount_due, user_id, force=False, note=None):
        """
        Registra la parte fiada de una venta como movimiento DEBT.

        IMPORTANTE: recibe `cur` de una transacción ya abierta por quien
        crea la venta (self.transaction()), para que la venta y la deuda
        se confirmen o se reviertan juntas. No abre su propia transacción.

        Valida límite de crédito antes de insertar. Si `force=True` (uso
        admin vía require_role), permite superar el límite igual.
        """
        cur.execute(
            "SELECT id, name, phone, credit_limit, status FROM customers WHERE id = ?",
            (customer_id,),
        )
        customer = cur.fetchone()
        if not customer:
            raise DatabaseError(f"Cliente {customer_id} no existe")

        credit_limit = customer[3]
        if credit_limit is not None and not force:
            current_balance = self.get_customer_balance(customer_id, cur=cur)
            if current_balance + amount_due > credit_limit:
                raise CreditLimitExceededError(
                    f"Cliente {customer_id} supera el límite de crédito "
                    f"({current_balance + amount_due:.2f} > {credit_limit:.2f})"
                )

        cur.execute(
            """
            INSERT INTO account_movements (customer_id, sell_id, type, amount, user_id, note)
            VALUES (?, ?, 'DEBT', ?, ?, ?)
            """,
            (customer_id, sell_id, amount_due, user_id, note),
        )

    def register_payment(self, customer_id, amount, user_id, note=None):
        """
        Registra un pago/abono. No permite pagar más de lo que el cliente debe.
        """
        if amount <= 0:
            raise DatabaseError("El monto del pago debe ser mayor a 0")

        current_balance = self.get_customer_balance(customer_id)
        if amount > current_balance:
            raise InsufficientBalanceError(
                f"El pago ({amount:.2f}) supera el saldo pendiente ({current_balance:.2f})"
            )

        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO account_movements (customer_id, sell_id, type, amount, user_id, note)
                VALUES (?, NULL, 'PAYMENT', ?, ?, ?)
                """,
                (customer_id, amount, user_id, note),
            )
            logger.info(f"[Credit] Pago registrado | cliente={customer_id} | monto={amount}")
            return cur.lastrowid

    def register_adjustment(self, customer_id, amount, user_id, note):
        """
        Ajuste manual (positivo o negativo). Requiere nota obligatoria
        para auditoría — no se permite un ajuste sin justificación.
        """
        if not note:
            raise DatabaseError("Todo ajuste de cuenta corriente requiere una nota")

        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO account_movements (customer_id, sell_id, type, amount, user_id, note)
                VALUES (?, NULL, 'ADJUSTMENT', ?, ?, ?)
                """,
                (customer_id, amount, user_id, note),
            )
            return cur.lastrowid