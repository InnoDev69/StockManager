import logging
import time
from functools import wraps
from tools.logger import logger

def measure_time(func):
    """Decorador para medir tiempo de ejecución de funciones."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if logger._level <= logging.DEBUG:
            start = time.perf_counter()
            result = func(*args, **kwargs)
            elapsed = (time.perf_counter() - start) * 1000  # en ms
            logger.info(f"{func.__name__} ejecutado en {elapsed:.2f}ms")
        return result
    return wrapper