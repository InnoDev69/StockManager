from enum import Enum


class View(str, Enum):
    """
    Centraliza las rutas de las plantillas HTML para la interfaz de Stockly.

    Esta enumeración mapea constantes descriptivas con sus respectivas rutas 
    relativas dentro del directorio 'templates'. Su uso en conjunto con 
    `render_template` de Flask previene errores tipográficos, activa el 
    autocompletado en el editor de código y permite refactorizar la estructura 
    de carpetas modificando los valores en un único lugar.

    Ejemplo de uso:
        from flask import render_template
        
        @app.route('/panel')
        def panel():
            return render_template(View.DASHBOARD)
    """

    # Auth
    LOGIN = "auth/login.html"
    RESET_PASSWORD = "auth/reset_password.html"
    USERS = "auth/users.html"
    
    # Core
    COMPONENTS = "core/components.html"
    
    # Errors
    ERROR_404 = "errors/404.html"
    ERROR_403 = "errors/403.html"
    ERROR_500 = "errors/500.html"
    UNDER_DEVELOPMENT = "errors/under_development.html"
    
    # Home
    DASHBOARD = "home/dashboard.html"
    METRICS = "home/metrics.html"
    
    # Products
    PRODUCTS_DETAIL = "products/product_detail.html"
    PRODUCTS_EDIT = "products/product_edit.html"
    PRODUCTS_EXPORT = "products/product_export.html"
    PRODUCTS_FORM = "products/product_form.html"
    PRODUCTS_MANAGEMENT = "products/product_management.html"
    
    # Inventory
    BARCODE_MANAGEMENT = "inventory/barcode_management.html"
    IMPORT_PRODUCTS = "inventory/import.html"
    STOCK_SCAN = "inventory/stock_scan.html"
    
    # Sales
    SALES_EDIT = "sales/sale_edit.html"
    SALES_FORM = "sales/sale_form.html"
    SALES_MANAGEMENT = "sales/sales.html"
    
    # System
    CHANGELOGS = "system/changelogs.html"
    CREDIT = "system/credit.html"
    HELP = "system/help.html"
    NOTIFICATIONS = "system/notifications.html"
    SETTINGS = "system/settings.html"
    
    # Base
    BASE = "base.html"