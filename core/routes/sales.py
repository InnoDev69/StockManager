from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from core.api.auth_utils import require_auth, require_permission
from core.bd.bdInstance import db
from miscellaneous import ROLES, PERMS

sales_bp = Blueprint('sales', __name__)

@sales_bp.route("/sales/new", methods=["GET", "POST"])
@require_auth
@require_permission(PERMS.SALES_CREATE)
def sale_new():
    """
    Crear una nueva venta.
    
    Requiere login: True.
    
    GET: Muestra formulario de venta
    POST: Procesa y registra la venta
    
    Form Data (POST):
        barcode (str): Código de barras del producto
        quantity (int): Cantidad vendida
    
    Returns:
        Template/Redirect: Formulario en GET, redirect a dashboard en POST
    """
    
    return render_template("sale_form.html", role=session.get("role", ROLES.VENDOR))

@sales_bp.route("/sales", methods=["GET"])
@require_auth
def sales():
    """
    Muestra el historial de ventas con filtros.
    
    Requiere login: True.
    
    Query Parameters:
        date_from (str, optional): Fecha inicial YYYY-MM-DD
        date_to (str, optional): Fecha final YYYY-MM-DD
        product (str, optional): Filtro por nombre de producto
        vendedor (str, optional): Filtro por nombre de vendedor
    
    Returns:
        Template: sales.html con datos de ventas filtrados
    """
    
    # Obtener parámetros de filtro
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    product_q = request.args.get("product", "").strip()
    vendedor_q = request.args.get("vendedor", "").strip()
    
    # Construir WHERE clause dinámico
    where_clauses = ["1=1"]
    params = []
    
    if date_from:
        where_clauses.append("DATE(s.date) >= ?")
        params.append(date_from)
    if date_to:
        where_clauses.append("DATE(s.date) <= ?")
        params.append(date_to)
    if product_q:
        where_clauses.append("i.name LIKE ?")
        params.append(f"%{product_q}%")
    if vendedor_q:
        where_clauses.append("s.vendor_id IN (SELECT id FROM users WHERE username LIKE ? OR email LIKE ?)")
        params.append(f"%{vendedor_q}%")
        params.append(f"%{vendedor_q}%")
    
    where_clause = " AND ".join(where_clauses)
    
    # Ejecutar consulta con filtros
    sales_data = db.execute_query(
        f"SELECT s.id, s.date, i.name, d.quantity, d.price, s.vendor_id, s.payment_method "
        f"FROM sells s "
        f"JOIN details d ON s.id = d.sell_id "
        f"JOIN items i ON d.item_id = i.id "
        f"WHERE {where_clause} "
        f"ORDER BY s.date DESC",
        tuple(params)
    )
    
    # Agrupar por venta
    sales_dict = {}
    for row in sales_data:
        sale_id = row[0]
        if sale_id not in sales_dict:
            sales_dict[sale_id] = {
                "id": sale_id,
                "date": row[1],
                "products": [],
                "total": 0.0,
                "total_quantity": 0,
                "vendedor": db.get_username_by_id(row[5]) if db.get_username_by_id(row[5]) else "unknown",
                "payment_method": row[6]
            }
        
        sales_dict[sale_id]["products"].append({
            "name": row[2],
            "quantity": row[3],
            "price": row[4]
        })
        sales_dict[sale_id]["total"] += row[3] * row[4]
        sales_dict[sale_id]["total_quantity"] += row[3]
    
    sales = list(sales_dict.values())
    return render_template("sales.html", sales=sales, role=session.get("role", ROLES.VENDOR))

@sales_bp.route("/sales/<int:sale_id>/edit", methods=["GET"])
@require_permission(PERMS.SALES_EDIT)
def edit_sale_form(sale_id):
    """
    Muestra formulario para editar una venta.
    Solo admins pueden acceder.
    """
    sale = db.get_sale_by_id(sale_id)
    if not sale:
        flash("Venta no encontrada", "error")
        return redirect(url_for("sales.sales"))
    
    return render_template("sale_edit.html", sale=sale, role=session.get("role", ROLES.VENDOR))