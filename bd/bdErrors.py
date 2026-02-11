"""
Excepciones personalizadas para operaciones de base de datos.

Este módulo define las excepciones específicas del dominio para manejar
errores relacionados con la persistencia de datos y lógica de negocio.
"""


class DatabaseError(Exception):
    """
    Excepción base para todos los errores relacionados con la base de datos.
    
    Se lanza cuando ocurre un error durante operaciones de SQLite que no puede
    ser manejado automáticamente (queries malformados, violaciones de constraints,
    errores de conexión, etc.).
    
    Args:
        message (str): Descripción del error de base de datos
    
    Example:
        >>> raise DatabaseError("No se pudo conectar a la base de datos")
    """
    pass


class StockError(DatabaseError):
    """
    Excepción para errores relacionados con operaciones de inventario.
    
    Se lanza cuando una operación de stock falla debido a reglas de negocio
    (ej: intentar vender más productos de los disponibles, stock negativo).
    
    Args:
        message (str): Descripción del error de stock
    
    Example:
        >>> raise StockError("Stock insuficiente para completar la venta")
    """
    pass