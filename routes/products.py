import csv
import io
import time
import uuid
from api.auth_utils import require_auth, require_admin, require_role
from data.roles import ROLES
from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify, send_file
from api.notifications_api import notify_user
from bd.bdInstance import db
from bd.bdConector import ValidationError
from tools.logger import logger

try:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import cm
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import black, gray
    from reportlab.lib.utils import ImageReader
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


products_bp = Blueprint('products', __name__)

temp_imports = {}
TEMP_IMPORT_MAX_AGE = 1800  # 30 minutos
TEMP_IMPORT_MAX_ENTRIES = 20

def cleanup_temp_imports():
    """Elimina importaciones temporales expiradas (>30 min) o si hay demasiadas."""
    now = time.time()
    expired = [k for k, v in temp_imports.items()
               if now - v.get("created_at", 0) > TEMP_IMPORT_MAX_AGE]
    for k in expired:
        del temp_imports[k]
    
    # Si aún hay demasiadas, eliminar las más antiguas
    if len(temp_imports) > TEMP_IMPORT_MAX_ENTRIES:
        sorted_keys = sorted(temp_imports, key=lambda k: temp_imports[k].get("created_at", 0))
        for k in sorted_keys[:len(temp_imports) - TEMP_IMPORT_MAX_ENTRIES]:
            del temp_imports[k]

@products_bp.route("/products/new", methods=["GET"])
@require_role(ROLES.ADMIN, ROLES.ROOT)
def product_new():
    """
    Muestra el formulario para crear un nuevo producto.
    
    Solo usuarios con rol 'admin' pueden acceder.
    La creación se realiza via API JSON (POST /api/products).
    
    Requiere login: True.
    
    Returns:
        Template: product_form.html (vacío, se envía por AJAX)
    """
    return render_template("product_form.html", form_data={}, role=session.get("role", ROLES.VENDOR), show_back=False)
        
#Compatibilidad
def legacy_product_form():
    return redirect(url_for("products.product_new"))

@products_bp.route("/product_management")
@require_role(ROLES.ADMIN, ROLES.ROOT)
def product_management():
    """
    Página de administración de productos.
    
    Permite ver, editar y eliminar productos del inventario.
    Solo accesible para usuarios autenticados.
    
    Requiere login: True.
    
    Returns:
        Template: product_management.html con la interfaz de gestión
    """
    
    return render_template("product_management.html", role=session.get("role", ROLES.VENDOR))

@products_bp.route("/import", methods=["GET", "POST"])
@require_role(ROLES.ADMIN, ROLES.ROOT)
def import_preview():
    """
    Vista previa de importación CSV.
    
    Solo administradores pueden importar productos.
    Muestra las primeras filas del CSV para mapear columnas.
    
    Requiere login: True.
    
    Returns:
        Template: import.html con formulario de importación
        JSON: Vista previa de datos si es POST (legacy support)
    """
    
    if request.method == "GET":
        return render_template("import.html", role=session.get("role", ROLES.VENDOR))
    
    if 'file' not in request.files:
        return {"error": "No file"}, 400
    
    file = request.files['file']
    delimiter = request.form.get('delimiter', ',')
    has_header = request.form.get('has_header') == '1'
    
    content = file.read().decode('utf-8')
    reader = csv.reader(io.StringIO(content), delimiter=delimiter)
    rows = list(reader)
    
    if not rows:
        return {"error": "Empty file"}, 400
    
    headers = rows[0] if has_header else [f"Col{i}" for i in range(len(rows[0]))]
    data_rows = rows[1:] if has_header else rows
    
    cleanup_temp_imports()
    
    temp_key = str(uuid.uuid4())
    temp_imports[temp_key] = {
        'headers': headers,
        'rows': data_rows,
        'delimiter': delimiter,
        'created_at': time.time()
    }
    
    return {
        'temp_key': temp_key,
        'headers': headers,
        'rows': data_rows[:10]
    }
    
@products_bp.route("/import/confirm", methods=["POST"])
@require_role(ROLES.ADMIN, ROLES.ROOT)
def confirm_import():
    """
    Confirmar e importar productos desde CSV.
    
    Procesa el archivo CSV temporal, mapea columnas según configuración
    del usuario e inserta productos en la base de datos.
    
    Requiere login: True.
    
    Form Data:
        temp_key (str): UUID del archivo temporal
        col_barcode (int): Índice de columna para código de barras
        col_name (int): Índice de columna para nombre
        col_description (int): Índice de columna para descripción
        col_quantity (int): Índice de columna para cantidad
        col_min_quantity (int): Índice de columna para stock mínimo
        col_price (int): Índice de columna para precio
    
    Returns:
        Redirect: A dashboard con mensaje de productos importados
    """
    
    temp_key = request.form.get('temp_key')
    if temp_key not in temp_imports:
        flash("Sesión expirada, vuelve a subir el CSV", "error")
        return redirect(url_for('products.import_preview'))
    
    data = temp_imports.pop(temp_key)
    rows = data['rows']
    
    col_barcode = int(request.form.get('col_barcode', 0))
    col_name = int(request.form.get('col_name', 1))
    col_description = int(request.form.get('col_description', 2))
    col_quantity = int(request.form.get('col_quantity', 3))
    col_min_quantity = int(request.form.get('col_min_quantity', 4))
    col_price = int(request.form.get('col_price', 5))
    col_expiration_date = request.form.get('col_expiration_date')
    col_expiration_date = int(col_expiration_date) if col_expiration_date else None
    
    imported = 0
    for row in rows:
        if len(row) <= max(col_barcode, col_name, col_quantity, col_price):
            continue
        
        barcode = row[col_barcode].strip()
        name = row[col_name].strip()
        desc = row[col_description].strip() if col_description < len(row) else ""
        qty = int(row[col_quantity]) if row[col_quantity].isdigit() else 0
        min_qty = int(row[col_min_quantity]) if col_min_quantity < len(row) and row[col_min_quantity].isdigit() else 0
        exp_date = row[col_expiration_date].strip() if col_expiration_date is not None and col_expiration_date < len(row) else None
        price = float(row[col_price]) if col_price < len(row) else 0.0
        
        db.add_item(barcode, desc, name, qty, min_qty, exp_date, price)
        imported += 1
    
    flash(f"{imported} productos importados correctamente")
    return redirect(url_for('dashboard.index'))

@products_bp.route("/products/<int:product_id>")
@require_auth
def product_detail(product_id):
    """
    Detalles de un producto específico.
    
    Muestra información completa del producto, incluyendo stock y fecha de vencimiento.
    Solo usuarios autenticados pueden acceder.
    
    Requiere login: True.
    
        Args:
                product_id (int): ID del producto a mostrar
    
    """
    product = db.get_item_by_id(product_id)
    return render_template("product_detail.html", product=product, role=session.get("role", ROLES.VENDOR),show_back=False)

@products_bp.route("/products/<int:product_id>/edit")
@require_role(ROLES.ADMIN, ROLES.ROOT)
def product_edit(product_id):
    """
    Página de edición de un producto existente.
    
    Permite modificar todos los campos de un producto excepto el código de barras.
    Solo accesible para usuarios con rol 'admin'.
    
    Requiere login: True.
    Requiere rol: admin.
    
    Args:
        product_id (int): ID del producto a editar
    
    Returns:
        Template: product_edit.html con formulario prelleno
        Redirect: 404 si el producto no existe
    """
    product = db.get_item_by_id(product_id)
    if not product:
        flash("Producto no encontrado", "error")
        return redirect(url_for("products.product_management", show_back='0'),)
    
    return render_template("product_edit.html", product=product, role=session.get("role", ROLES.VENDOR), show_back=False)

@products_bp.route("/products/barcodes", methods=["GET"])
@require_role(ROLES.ADMIN, ROLES.ROOT)
def barcode_management():
    """
    Panel de gestión de códigos de barras.
    Solo visible para administradores.
    """
    products = db.get_all_items()
    
    # Contar productos sin código
    without_barcode = [p for p in products if not p.get('barrs_code')]
    
    return render_template("barcode_management.html", 
                         products=products,
                         without_barcode=without_barcode,
                         role=session.get("role", ROLES.VENDOR))

@products_bp.route("/products/<int:product_id>/barcode/image", methods=["GET"])
@require_auth
def get_barcode_image(product_id):
    """
    Retorna la imagen PNG del código de barras de un producto.
    """
    try:
        product = db.get_item_details(product_id)
        
        if not product or not product.get('barrs_code'):
            return jsonify({"error": "Producto sin código de barras"}), 404
        
        img_io = db.generate_barcode_image(product['barrs_code'])
        return send_file(img_io, mimetype='image/png')
        
    except Exception as e:
        logger.error(f"Error generando código de barras: {e}")
        return jsonify({"error": str(e)}), 500

@products_bp.route("/products/<int:product_id>/barcode/regenerate", methods=["POST"])
@require_role(ROLES.ADMIN, ROLES.ROOT)
def regenerate_barcode(product_id):
    """
    Regenera/asigna un nuevo código de barras automático a un producto.
    """
    try:
        new_code = f"PRD{product_id:06d}"
        db.update_item_barcode(product_id, new_code)
        
        return jsonify({
            "success": True,
            "message": f"Código de barras actualizado a: {new_code}",
            "barrs_code": new_code
        }), 200
        
    except Exception as e:
        logger.error(f"Error regenerando código: {e}")
        return jsonify({"error": str(e)}), 500

@products_bp.route("/products/<int:product_id>/barcode/update", methods=["PUT"])
@require_role(ROLES.ADMIN, ROLES.ROOT)
def update_barcode_manual(product_id):
    """
    Actualiza manualmente el código de barras de un producto.
    """
    try:
        data = request.get_json()
        new_code = data.get('barrs_code', '').strip()
        
        if not new_code:
            return jsonify({"error": "Código de barras no puede estar vacío"}), 400
        
        db.update_item_barcode(product_id, new_code)
        
        return jsonify({
            "success": True,
            "message": f"Código actualizado a: {new_code}",
            "barrs_code": new_code
        }), 200
        
    except Exception as e:
        logger.error(f"Error actualizando código: {e}")
        return jsonify({"error": str(e)}), 500

@products_bp.route("/products/barcodes/pdf", methods=["GET"])
@require_role(ROLES.ADMIN, ROLES.ROOT)
def download_barcodes_pdf():
    """
    Descarga un PDF con los códigos de barras seleccionados.
    Optimizado para impresión sin desperdiciar papel.
    
    Parámetros: ids (lista de IDs separados por comas)
    """
    if not HAS_REPORTLAB:
        return jsonify({"error": "Librería reportlab no instalada. Instala con: pip install reportlab pillow"}), 500
    
    try:
        ids_str = request.args.get('ids', '')
        if not ids_str:
            return jsonify({"error": "No hay productos seleccionados"}), 400
        
        product_ids = [int(id) for id in ids_str.split(',') if id.strip().isdigit()]
        if not product_ids:
            return jsonify({"error": "IDs inválidos"}), 400
        
        all_products = db.get_all_items()
        products = [p for p in all_products if p.get('id') in product_ids and p.get('barrs_code')]
        
        if not products:
            return jsonify({"error": "No hay productos con código de barras"}), 400
        
        pdf_io = io.BytesIO()
        
        page_width, page_height = landscape(A4)
        
        cols = 3
        rows = 5
        margin = 0.5 * cm
        cell_width = (page_width - 2 * margin) / cols
        cell_height = (page_height - 2 * margin) / rows
        
        # Crear PDF
        c = canvas.Canvas(pdf_io, pagesize=landscape(A4))
        c.setTitle("Códigos de Barras")
        
        idx = 0
        page_idx = 0
        
        for idx, product in enumerate(products):
            if idx > 0 and idx % (cols * rows) == 0:
                c.showPage()
                page_idx += 1
            
            pos_in_page = idx % (cols * rows)
            row = pos_in_page // cols
            col = pos_in_page % cols
            
            x = margin + col * cell_width
            y = page_height - margin - (row + 1) * cell_height
            
            c.setLineWidth(0.5)
            c.setStrokeColor(gray)
            c.rect(x, y, cell_width, cell_height)
            
            try:
                img_io = db.generate_barcode_image(product['barrs_code'])
                img_io.seek(0)
                
                img_width = cell_width * 0.8
                img_height = cell_height * 0.55
                img_x = x + (cell_width - img_width) / 2
                img_y = y + cell_height * 0.35
                
                c.drawImage(ImageReader(img_io), img_x, img_y, width=img_width, height=img_height, preserveAspectRatio=True)
            except Exception as e:
                logger.error(f"Error dibujando barcode para {product.get('id')}: {e}")
            
            code_text = product['barrs_code']
            code_y = y + cell_height * 0.15
            c.setFont("Helvetica", 8)
            c.drawCentredString(x + cell_width / 2, code_y, code_text)
            
            name_text = product.get('name', '')[:20]
            name_y = y + 5
            c.setFont("Helvetica", 7)
            c.drawCentredString(x + cell_width / 2, name_y, name_text)
        
        c.showPage()
        c.save()
        
        pdf_io.seek(0)
        return send_file(
            pdf_io,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'codigos_barras_{int(time.time())}.pdf'
        )
        
    except ValueError as e:
        logger.error(f"Error en parámetros PDF: {e}")
        return jsonify({"error": "IDs inválidos"}), 400
    except Exception as e:
        logger.error(f"Error generando PDF: {e}")
        return jsonify({"error": str(e)}), 500