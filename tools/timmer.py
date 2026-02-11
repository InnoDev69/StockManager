"""
Utilidades para medición de rendimiento.

Este módulo proporciona decoradores para instrumentar código y medir
tiempos de ejecución, útil para identificar cuellos de botella y optimizar
operaciones críticas (queries de BD, procesamiento de archivos, etc.).
"""
import time
from functools import wraps
from tools.logger import logger

def measure_time(func):
    """
    Decorador que mide y loggea el tiempo de ejecución de una función.
    
    Útil para monitorear el rendimiento de operaciones que pueden volverse
    lentas con el crecimiento de datos (queries, imports, backups).
    
    Args:
        func (callable): Función a instrumentar
    
    Returns:
        callable: Función decorada que loggea su tiempo de ejecución
    
    Example:
        >>> @measure_time
        ... def process_large_csv():
        ...     # procesar datos
        ...     pass
        >>> process_large_csv()
        # INFO: process_large_csv ejecutado en 1234.56ms
    
    Note:
        Usa time.perf_counter() para máxima precisión.
        El overhead del decorador es despreciable (<1µs).
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = (time.perf_counter() - start) * 1000  # convertir a milisegundos
        logger.info(f"{func.__name__} ejecutado en {elapsed:.2f}ms")
        return result
    return wrapper