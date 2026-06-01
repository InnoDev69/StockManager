import os
from flask import Blueprint, render_template, session, redirect
from bd.bdInstance import db
from data.roles import ROLES

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route("/")
def index():
    """
    Dashboard principal de la aplicación.
    
    Muestra estadísticas generales:
    - Total de productos
    - Productos con stock bajo
    - Ventas del día
    - Lista de productos con stock crítico
    
    Requiere login: True.
    
    Returns:
        Template: dashboard.html con estadísticas y datos del usuario
    """
    
    if not session.get("user_id"):
        return redirect("/login")
    
    stats_data = db.get_dashboard_stats()
    stats = {
        "products": stats_data.get("products", 0),
        "low_stock": stats_data.get("low_stock", 0),
        "sales_today": stats_data.get("sales_today", 0)
    }
    low_stock_list = stats_data.get("low_stock_list", [])
    
    out_of_stock = db.execute_query("SELECT COUNT(*) FROM items WHERE quantity = 0 AND status = 1")[0][0]
    stats["out_of_stock"] = out_of_stock
    
    role = session.get("role", ROLES.VENDOR)
    return render_template('dashboard.html', stats=stats, role=role,
                       low_stock_list=low_stock_list, products=[], show_back=False,
                       DEBUG=1 if os.getenv("DEBUG", "0") == "1" else 0)