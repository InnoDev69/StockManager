import datetime

class Limits:
    """Límites de caracteres y valores para validación."""
    
    # Items/Productos
    ITEM_NAME_MAX = 25
    ITEM_DESCRIPTION_MAX = 200
    ITEM_BARCODE_MAX = 20
    ITEM_QUANTITY_MAX = 10000
    ITEM_MIN_QUANTITY_MAX = 1000
    ITEM_PRICE_MAX = 1000000.00
    ITEM_ATRIBUTE_NAME_MAX = 30
    ITEM_ATRIBUTE_VALUE_MAX = 50
    ITEM_EXPIRATION_DATE_MAX = 10  # Formato YYYY-MM-DD
    
    # Usuarios
    USER_USERNAME_MAX = 30
    USER_PASSWORD_MAX = 128
    USER_EMAIL_MAX = 100
    USER_ROLE_MAX = 20
    USER_CODE_MAX = 6
    
    # Calendario
    CALENDAR_YEAR_MAX = datetime.datetime.now().year + 10
    CALENDAR_YEAR_MIN = datetime.datetime.now().year - 1