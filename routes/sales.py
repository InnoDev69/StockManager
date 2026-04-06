from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from bd.bdInstance import db

sales_bp = Blueprint('sales', __name__)

@sales_bp.route("/sales/new", methods=["GET", "POST"])
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
    
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))
    if request.method == "GET":
        return render_template("sale_form.html")
    barcode = request.form.get("barcode", "").strip()
    try:
        qty = int(request.form.get("quantity", "1"))
    except ValueError:
        return render_template("sale_form.html", error="Cantidad inválida")

    item = db.get_item_by_barcode(barcode)
    if not item:
        return render_template("sale_form.html", error="Producto no encontrado")

    # item: (id, barrs_code, name, description, quantity, price)
    item_id, barrs_code, name, description, stock, price = item

    if stock < qty:
        return render_template("sale_form.html", error="Stock insuficiente")
    db.record_sale(item_id, qty)
    flash(f"Venta registrada: {name} x{qty}")
    return redirect(url_for("dashboard.index"))

@sales_bp.route("/sales", methods=["GET"])
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
    
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))
    
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
        where_clauses.append("s.vendedor LIKE ?")
        params.append(f"%{vendedor_q}%")
    
    where_clause = " AND ".join(where_clauses)
    
    # Ejecutar consulta con filtros
    sales_data = db.execute_query(
        f"SELECT s.id, s.date, i.name, d.quantity, d.price, s.vendedor, s.payment_method "
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
                "vendedor": row[5],
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
    return render_template("sales.html", sales=sales)