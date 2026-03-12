from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
from bd.bdInstance import db
from api.auth_utils import require_auth

metrics_api = Blueprint("metrics_api", __name__)

@metrics_api.route("/stats", methods=["GET"])
def get_stats():
    """
    Obtiene estadísticas del dashboard.
    
    Requiere login: True.
    
    Returns:
        JSON: Estadísticas del sistema
        - products (int): Total de productos
        - low_stock (int): Productos con stock bajo
        - sales_today (int): Ventas realizadas hoy
        - low_stock_list (array): Top 10 productos con stock crítico
          - id (int): ID del producto
          - name (str): Nombre
          - sku (str): Código de barras
          - stock (int): Cantidad actual
    
    Status Codes:
        200: Estadísticas obtenidas exitosamente
        401: No autorizado
    """
    
    auth_error = require_auth()
    if auth_error:
        return auth_error
    
    total_products = db.execute_query("SELECT COUNT(*) FROM items")[0][0]
    
    low_stock = db.execute_query(
        "SELECT COUNT(*) FROM items WHERE quantity <= min_quantity AND quantity > 0"
    )[0][0]
    
    sales_today = db.execute_query(
        "SELECT COUNT(*) FROM sells WHERE DATE(date) = DATE('now')"
    )[0][0]
    
    low_stock_items = db.execute_query(
        "SELECT id, name, barrs_code, quantity FROM items WHERE quantity <= min_quantity ORDER BY quantity ASC LIMIT 10"
    )
    
    low_stock_list = [
        {
            "id": row[0],
            "name": row[1],
            "sku": row[2],
            "stock": row[3]
        }
        for row in low_stock_items
    ]
    
    return jsonify({
        "products": total_products,
        "low_stock": low_stock,
        "sales_today": sales_today,
        "low_stock_list": low_stock_list
    }), 200
    
@metrics_api.route('/metrics', methods=['GET'])
def get_metrics():
    """
    Obtiene métricas del negocio para el dashboard de analytics.
    
    Requiere login: True.
    
    Query params:
        - period (int): Número de días (7, 30, 90, 365)
        - from (str): Fecha inicio (YYYY-MM-DD)
        - to (str): Fecha fin (YYYY-MM-DD)
    
    Returns:
        JSON: Métricas completas del negocio
    """
    
    auth_error = require_auth()
    if auth_error:
        return auth_error
    
    period = request.args.get('period', 7, type=int)
    date_from = request.args.get('from')
    date_to = request.args.get('to')
    
    if date_from and date_to:
        start_date = date_from
        end_date = date_to
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        period_days = (end_dt - start_dt).days + 1
    else:
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=period - 1)).strftime('%Y-%m-%d')
        period_days = period
    
    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
    prev_end_date = (start_dt - timedelta(days=1)).strftime('%Y-%m-%d')
    prev_start_date = (start_dt - timedelta(days=period_days)).strftime('%Y-%m-%d')
    
    data = db.get_metrics_data(start_date, end_date, prev_start_date, prev_end_date)
    
    revenue = float(data["kpis"][0])
    total_sales = int(data["kpis"][1])
    units_sold = int(data["kpis"][2])
    avg_ticket = round(revenue / total_sales, 2) if total_sales > 0 else 0
    
    prev_revenue = float(data["prev_kpis"][0])
    prev_total_sales = int(data["prev_kpis"][1])
    prev_avg_ticket = round(prev_revenue / prev_total_sales, 2) if prev_total_sales > 0 else 0
    prev_units_sold = int(data["prev_kpis"][2])
    
    def calc_change(current, previous):
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        return round(((current - previous) / previous) * 100, 1)
    
    revenue_change = calc_change(revenue, prev_revenue)
    sales_change = calc_change(total_sales, prev_total_sales)
    ticket_change = calc_change(avg_ticket, prev_avg_ticket)
    units_change = calc_change(units_sold, prev_units_sold)
    
    date_range = {}
    current_dt = datetime.strptime(start_date, '%Y-%m-%d')
    end_dt = datetime.strptime(end_date, '%Y-%m-%d')
    while current_dt <= end_dt:
        date_range[current_dt.strftime('%Y-%m-%d')] = {"revenue": 0, "sales": 0}
        current_dt += timedelta(days=1)
    
    for row in data["sales_over_time"]:
        date_str = row[0] if isinstance(row[0], str) else row[0].strftime('%Y-%m-%d')
        if date_str in date_range:
            date_range[date_str] = {"revenue": float(row[1]), "sales": int(row[2])}
    
    days_es = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
    labels, revenues, sales_counts = [], [], []
    for date_str in sorted(date_range):
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        labels.append(days_es[dt.weekday()] if period_days <= 7 else dt.strftime('%d/%m'))
        revenues.append(date_range[date_str]["revenue"])
        sales_counts.append(date_range[date_str]["sales"])
    
    top_products = [
        {"id": r[0], "name": r[1], "sku": r[2] or "Sin SKU", "units": int(r[3]), "revenue": float(r[4])}
        for r in data["top_products"]
    ]
    
    sales_by_weekday = [0] * 7
    for row in data["weekday_sales"]:
        sqlite_wd = int(row[0])
        adjusted = (sqlite_wd - 1) if sqlite_wd > 0 else 6
        sales_by_weekday[adjusted] = int(row[1])
    
    sales_by_hour = [0] * 24
    for row in data["hourly_sales"]:
        sales_by_hour[int(row[0])] = int(row[1])
    
    out_of_stock = int(data["alerts"][0] or 0)
    low_stock = int(data["alerts"][1] or 0)
    no_movement = int(data["alerts"][2] or 0)
    
    days_names = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    
    best_day = None
    if data["best_weekday_idx"] is not None:
        best_day = {
            "name": days_names[data["best_weekday_idx"]],
            "revenue": data["best_day_revenue"]
        }
    
    peak_hour = sales_by_hour.index(max(sales_by_hour)) if any(sales_by_hour) else None
    top_product = {"name": top_products[0]["name"], "units": top_products[0]["units"]} if top_products else None
    
    if prev_revenue > 0:
        if revenue_change > 10:
            trend = f"Las ventas aumentaron {revenue_change}% respecto al período anterior. ¡Excelente trabajo!"
        elif revenue_change > 0:
            trend = f"Las ventas aumentaron {revenue_change}% respecto al período anterior. Buen progreso."
        elif revenue_change > -10:
            trend = f"Las ventas disminuyeron {abs(revenue_change)}% respecto al período anterior. Considera revisar tu estrategia."
        else:
            trend = f"Las ventas cayeron {abs(revenue_change)}% respecto al período anterior. Se recomienda tomar acción."
    else:
        trend = "No hay datos del período anterior para comparar."
    
    return jsonify({
        "kpis": {
            "revenue": round(revenue, 2),
            "totalSales": total_sales,
            "avgTicket": avg_ticket,
            "unitsSold": units_sold,
            "revenueChange": revenue_change,
            "salesChange": sales_change,
            "ticketChange": ticket_change,
            "unitsChange": units_change
        },
        "salesOverTime": {
            "labels": labels,
            "revenue": revenues,
            "sales": sales_counts
        },
        "topProducts": top_products,
        "salesByWeekday": sales_by_weekday,
        "salesByHour": sales_by_hour,
        "comparison": {
            "current": round(revenue, 2),
            "previous": round(prev_revenue, 2)
        },
        "alerts": {
            "outOfStock": out_of_stock,
            "lowStock": low_stock,
            "noMovement": no_movement
        },
        "insights": {
            "bestDay": best_day,
            "peakHour": peak_hour,
            "topProduct": top_product,
            "trend": trend
        },
        "period": {
            "start": start_date,
            "end": end_date,
            "days": period_days
        }
    }), 200