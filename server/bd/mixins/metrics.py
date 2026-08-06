class MetricsMixin:
    """Métodos de métricas y reportes del negocio."""

    def _get_debtors_snapshot(self):
        """Devuelve clientes con saldo pendiente y el total adeudado."""
        with self._cursor() as cur:
            cur.execute(
                """
                WITH balances AS (
                    SELECT
                        c.id,
                        c.name,
                        c.phone,
                        c.credit_limit,
                        COALESCE(SUM(
                            CASE
                                WHEN m.type = 'DEBT' THEN m.amount
                                WHEN m.type = 'PAYMENT' THEN -m.amount
                                WHEN m.type = 'ADJUSTMENT' THEN m.amount
                            END
                        ), 0) AS balance
                    FROM customers c
                    LEFT JOIN account_movements m ON m.customer_id = c.id
                    WHERE c.status = 1
                    GROUP BY c.id, c.name, c.phone, c.credit_limit
                )
                SELECT id, name, phone, credit_limit, balance
                FROM balances
                WHERE balance > 0
                ORDER BY balance DESC, name ASC
                LIMIT 10
                """
            )
            debtors = cur.fetchall()

            cur.execute(
                """
                WITH balances AS (
                    SELECT
                        c.id,
                        COALESCE(SUM(
                            CASE
                                WHEN m.type = 'DEBT' THEN m.amount
                                WHEN m.type = 'PAYMENT' THEN -m.amount
                                WHEN m.type = 'ADJUSTMENT' THEN m.amount
                            END
                        ), 0) AS balance
                    FROM customers c
                    LEFT JOIN account_movements m ON m.customer_id = c.id
                    WHERE c.status = 1
                    GROUP BY c.id
                )
                SELECT COUNT(*), COALESCE(SUM(balance), 0)
                FROM balances
                WHERE balance > 0
                """
            )
            debt_summary = cur.fetchone()

        return {
            "items": debtors,
            "count": int(debt_summary[0] or 0),
            "totalDebt": float(debt_summary[1] or 0),
        }

    def _fetch_period_metrics(self, start_date, end_date):
        """Obtiene métricas de un período usando ingresos cobrados, no facturación bruta."""
        with self._cursor() as cur:
            cur.execute(
                """
                WITH sale_totals AS (
                    SELECT
                        s.id AS sell_id,
                        DATE(s.date) AS sale_date,
                        COALESCE(s.amount_paid, SUM(d.quantity * d.price)) AS collected_amount,
                        SUM(d.quantity * d.price) AS gross_amount,
                        SUM(d.quantity) AS units_sold
                    FROM sells s
                    JOIN details d ON d.sell_id = s.id
                    WHERE DATE(s.date) BETWEEN ? AND ?
                    GROUP BY s.id
                ),
                payment_totals AS (
                    SELECT
                        DATE(date) AS payment_date,
                        SUM(amount) AS collected_amount
                    FROM account_movements
                    WHERE type = 'PAYMENT'
                      AND DATE(date) BETWEEN ? AND ?
                    GROUP BY DATE(date)
                )
                SELECT
                    COALESCE((SELECT SUM(collected_amount) FROM sale_totals), 0) + COALESCE((SELECT SUM(collected_amount) FROM payment_totals), 0),
                    COALESCE((SELECT COUNT(*) FROM sale_totals), 0),
                    COALESCE((SELECT SUM(units_sold) FROM sale_totals), 0),
                    COALESCE((SELECT SUM(gross_amount) FROM sale_totals), 0),
                    COALESCE((SELECT SUM(collected_amount) FROM sale_totals), 0),
                    COALESCE((SELECT SUM(collected_amount) FROM payment_totals), 0)
                """,
                (start_date, end_date, start_date, end_date),
            )
            kpis = cur.fetchone()

            cur.execute(
                """
                WITH sale_daily AS (
                    SELECT
                        DATE(s.date) AS day,
                        SUM(COALESCE(s.amount_paid, totals.gross_amount)) AS collected_amount,
                        COUNT(DISTINCT s.id) AS sales_count
                    FROM sells s
                    JOIN (
                        SELECT sell_id, SUM(quantity * price) AS gross_amount
                        FROM details
                        GROUP BY sell_id
                    ) totals ON totals.sell_id = s.id
                    WHERE DATE(s.date) BETWEEN ? AND ?
                    GROUP BY DATE(s.date)
                ),
                payment_daily AS (
                    SELECT DATE(date) AS day, SUM(amount) AS collected_amount, 0 AS sales_count
                    FROM account_movements
                    WHERE type = 'PAYMENT'
                      AND DATE(date) BETWEEN ? AND ?
                    GROUP BY DATE(date)
                )
                SELECT day, SUM(collected_amount) AS revenue, SUM(sales_count) AS sales
                FROM (
                    SELECT * FROM sale_daily
                    UNION ALL
                    SELECT * FROM payment_daily
                )
                GROUP BY day
                ORDER BY day ASC
                """,
                (start_date, end_date, start_date, end_date),
            )
            sales_over_time = cur.fetchall()

            cur.execute(
                """
                SELECT
                    i.id,
                    i.name,
                    i.barrs_code,
                    SUM(d.quantity),
                    SUM(d.quantity * d.price)
                FROM details d
                JOIN items i ON d.item_id = i.id
                JOIN sells s ON d.sell_id = s.id
                WHERE DATE(s.date) BETWEEN ? AND ?
                GROUP BY i.id, i.name, i.barrs_code
                ORDER BY 4 DESC
                LIMIT 10
                """,
                (start_date, end_date),
            )
            top_products = cur.fetchall()

            cur.execute(
                """
                SELECT CAST(strftime('%w', s.date) AS INTEGER), COUNT(DISTINCT s.id)
                FROM sells s
                WHERE DATE(s.date) BETWEEN ? AND ?
                GROUP BY 1
                """,
                (start_date, end_date),
            )
            weekday_sales = cur.fetchall()

            cur.execute(
                """
                SELECT CAST(strftime('%H', s.date) AS INTEGER), COUNT(DISTINCT s.id)
                FROM sells s
                WHERE DATE(s.date) BETWEEN ? AND ?
                GROUP BY 1
                """,
                (start_date, end_date),
            )
            hourly_sales = cur.fetchall()

            cur.execute(
                """
                SELECT
                    SUM(CASE WHEN quantity = 0 AND status = 1 THEN 1 ELSE 0 END),
                    SUM(CASE WHEN quantity > 0 AND quantity <= min_quantity AND status = 1 THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status = 1 AND id NOT IN (
                        SELECT DISTINCT d.item_id FROM details d
                        JOIN sells s ON d.sell_id = s.id
                        WHERE DATE(s.date) >= DATE('now', '-30 days')
                    ) THEN 1 ELSE 0 END)
                FROM items
                """
            )
            alerts = cur.fetchone()

        return {
            "kpis": kpis,
            "sales_over_time": sales_over_time,
            "top_products": top_products,
            "weekday_sales": weekday_sales,
            "hourly_sales": hourly_sales,
            "alerts": alerts,
        }

    def get_metrics_data(self, start_date, end_date, prev_start_date, prev_end_date):
        """
        Obtiene todas las métricas del negocio en una sola conexión.

        Args:
            start_date (str): Fecha inicio periodo actual (YYYY-MM-DD)
            end_date (str): Fecha fin periodo actual (YYYY-MM-DD)
            prev_start_date (str): Fecha inicio periodo anterior (YYYY-MM-DD)
            prev_end_date (str): Fecha fin periodo anterior (YYYY-MM-DD)

        Returns:
            dict: Métricas completas del negocio
        """
        current = self._fetch_period_metrics(start_date, end_date)
        previous = self._fetch_period_metrics(prev_start_date, prev_end_date)
        debtors = self._get_debtors_snapshot()

        kpis = current["kpis"]
        prev_kpis = previous["kpis"]
        sales_over_time = current["sales_over_time"]
        top_products = current["top_products"]
        weekday_sales = current["weekday_sales"]
        hourly_sales = current["hourly_sales"]
        alerts = current["alerts"]

        return {
            "kpis": kpis,
            "prev_kpis": prev_kpis,
            "sales_over_time": sales_over_time,
            "top_products": top_products,
            "weekday_sales": weekday_sales,
            "hourly_sales": hourly_sales,
            "alerts": alerts,
            "debtors": debtors,
        }

    def get_vendors_metrics(self, start_date, end_date, prev_start_date, prev_end_date):
        """
        Obtiene métricas de desempeño por vendedor.

        Args:
            start_date (str): Fecha inicio periodo actual (YYYY-MM-DD)
            end_date (str): Fecha fin periodo actual (YYYY-MM-DD)
            prev_start_date (str): Fecha inicio periodo anterior (YYYY-MM-DD)
            prev_end_date (str): Fecha fin periodo anterior (YYYY-MM-DD)

        Returns:
            dict: Vendedores con sus métricas (ingresos, ventas, ticket promedio)
        """
        with self._cursor() as cur:
            # Vendedores actuales
            cur.execute("""
                SELECT 
                    u.id,
                    u.username,
                    COALESCE(SUM(COALESCE(s.amount_paid, totals.gross_amount)), 0) as revenue,
                    COUNT(DISTINCT s.id) as sales_count,
                    COALESCE(SUM(totals.units_sold), 0) as units_sold
                FROM users u
                INNER JOIN sells s ON u.id = s.vendor_id
                INNER JOIN (
                    SELECT sell_id, SUM(quantity * price) AS gross_amount, SUM(quantity) AS units_sold
                    FROM details
                    GROUP BY sell_id
                ) totals ON totals.sell_id = s.id
                WHERE u.status = 1 AND DATE(s.date) BETWEEN ? AND ?
                GROUP BY u.id, u.username
                ORDER BY revenue DESC
            """, (start_date, end_date))
            vendors_current = cur.fetchall()

            # Vendedores periodo anterior
            cur.execute("""
                SELECT 
                    u.id,
                    COALESCE(SUM(COALESCE(s.amount_paid, totals.gross_amount)), 0) as revenue,
                    COUNT(DISTINCT s.id) as sales_count
                FROM users u
                INNER JOIN sells s ON u.id = s.vendor_id
                INNER JOIN (
                    SELECT sell_id, SUM(quantity * price) AS gross_amount
                    FROM details
                    GROUP BY sell_id
                ) totals ON totals.sell_id = s.id
                WHERE u.status = 1 AND DATE(s.date) BETWEEN ? AND ?
                GROUP BY u.id
                """, (prev_start_date, prev_end_date))
            vendors_prev = {row[0]: {"revenue": row[1], "sales": row[2]} for row in cur.fetchall()}

        vendors_data = []
        for vendor in vendors_current:
            vendor_id, username, revenue, sales_count, units = vendor
            prev_data = vendors_prev.get(vendor_id, {"revenue": 0, "sales": 0})
            
            avg_ticket = round(revenue / sales_count, 2) if sales_count > 0 else 0
            prev_avg_ticket = round(prev_data["revenue"] / prev_data["sales"], 2) if prev_data["sales"] > 0 else 0
            
            revenue_change = round(((revenue - prev_data["revenue"]) / prev_data["revenue"] * 100), 1) if prev_data["revenue"] > 0 else (100 if revenue > 0 else 0)
            sales_change = round(((sales_count - prev_data["sales"]) / prev_data["sales"] * 100), 1) if prev_data["sales"] > 0 else (100 if sales_count > 0 else 0)

            vendors_data.append({
                "id": vendor_id,
                "name": username,
                "revenue": round(revenue, 2),
                "salesCount": int(sales_count),
                "unitsSold": int(units),
                "avgTicket": avg_ticket,
                "revenueChange": revenue_change,
                "salesChange": sales_change,
            })

        return vendors_data