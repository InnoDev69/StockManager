import logging
import os
import sys
from datetime import datetime

def get_log_dir():
    """
    Retorna el directorio de logs:
    - Desarrollo: ./logs (relativo al proyecto)
    - Producción (empaquetado): directorio de datos del usuario
    """
    # Si está congelado (PyInstaller), usar directorio de usuario

    if getattr(sys, 'frozen', False):
        if sys.platform == "win32":  # Windows
            base_dir = os.path.join(os.getenv("APPDATA"), "StockManager", "logs")
        else:  # macOS y Linux
            base_dir = os.path.join(os.path.expanduser("~"), ".stock_manager", "logs")
    else:
        base_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
    
    return base_dir
    
class AppLogger:
    """
    Logger centralizado para la aplicación.
    
    Uso:
        from debug.logger import logger
        
        logger.error("Mensaje de error")
        logger.warning("Advertencia")
        logger.info("Información")
        logger.debug("Debug")
    """
    
    _instance = None
    _logger = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._setup_logger()
        return cls._instance
    
    def _setup_logger(self):
        self._logger = logging.getLogger("StockManager")
        self._logger.setLevel(logging.DEBUG)
        
        #evita duplicar handlers
        if self._logger.handlers:
            return
        
        # formato del log
        formatter = logging.Formatter(
            fmt="[%(asctime)s] %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.WARNING)
        console_handler.setFormatter(formatter)
        self._logger.addHandler(console_handler)
        
        log_dir = get_log_dir()
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, f"app_{datetime.now().strftime('%Y%m%d')}.log")
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        self._logger.addHandler(file_handler)
    
    def error(self, message: str, exc_info: bool = False):
        """Log de error. exc_info=True para incluir traceback."""
        self._logger.error(message, exc_info=exc_info)
    
    def warning(self, message: str):
        """Log de advertencia."""
        self._logger.warning(message)
    
    def info(self, message: str):
        """Log informativo."""
        self._logger.info(message)
    
    def debug(self, message: str):
        """Log de debug (solo en archivo)."""
        self._logger.debug(message)
    
    def exception(self, message: str):
        """Log de excepción con traceback completo."""
        self._logger.exception(message)


logger = AppLogger()
