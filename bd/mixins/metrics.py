class MetricsMixin:
    """Métodos de métricas y reportes del negocio."""

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

            # Alertas combinadas
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
                    COALESCE(SUM(d.quantity * d.price), 0) as revenue,
                    COUNT(DISTINCT s.id) as sales_count,
                    COALESCE(SUM(d.quantity), 0) as units_sold
                FROM users u
                LEFT JOIN details d ON u.id = d.vendor_id
                LEFT JOIN sells s ON d.sell_id = s.id AND DATE(s.date) BETWEEN ? AND ?
                WHERE u.status = 1
                GROUP BY u.id, u.username
                ORDER BY revenue DESC
            """, (start_date, end_date))
            vendors_current = cur.fetchall()

            # Vendedores periodo anterior
            cur.execute("""
                SELECT 
                    u.id,
                    COALESCE(SUM(d.quantity * d.price), 0) as revenue,
                    COUNT(DISTINCT s.id) as sales_count
                FROM users u
                LEFT JOIN details d ON u.id = d.vendor_id
                LEFT JOIN sells s ON d.sell_id = s.id AND DATE(s.date) BETWEEN ? AND ?
                WHERE u.status = 1
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