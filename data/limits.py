"""
Constantes y límites de validación para la aplicación.

Este módulo centraliza todos los límites de longitud y valores numéricos
permitidos, facilitando el mantenimiento y asegurando consistencia entre
validación de frontend y backend.

Modificar estos valores afecta la validación en toda la aplicación.
"""

class Limits:
    """
    Límites de caracteres y valores numéricos para validación de entrada.
    
    Agrupa constantes relacionadas con productos, usuarios y otras entidades.
    Estos límites se aplican tanto en validadores Python como en constraints
    de la base de datos.
    
    Example:
        >>> from data.limits import Limits
        >>> if len(product_name) > Limits.ITEM_NAME_MAX:
        ...     raise ValidationError("Nombre muy largo")
    """
    
    # Límites para Items/Productos
    ITEM_NAME_MAX = 25              # Caracteres máximos para nombre de producto
    ITEM_DESCRIPTION_MAX = 200      # Caracteres máximos para descripción
    ITEM_BARCODE_MAX = 20           # Caracteres máximos para código de barras
    ITEM_QUANTITY_MAX = 10000       # Cantidad máxima en inventario
    ITEM_MIN_QUANTITY_MAX = 1000    # Stock mínimo máximo configurable
    ITEM_PRICE_MAX = 1000000.00     # Precio máximo permitido
    
    # Límites para Usuarios
    USER_USERNAME_MAX = 30          # Caracteres máximos para nombre de usuario
    USER_PASSWORD_MAX = 128         # Longitud máxima de contraseña hasheada
    USER_EMAIL_MAX = 100            # Caracteres máximos para email
    USER_ROLE_MAX = 20              # Caracteres máximos para rol