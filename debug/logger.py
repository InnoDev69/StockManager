import logging
import os
from datetime import datetime

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
        
        # Evitar duplicar handlers
        if self._logger.handlers:
            return
        
        # Formato del log
        formatter = logging.Formatter(
            fmt="[%(asctime)s] %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        
        # Handler para consola (solo errores y warnings)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.WARNING)
        console_handler.setFormatter(formatter)
        self._logger.addHandler(console_handler)
        
        # Handler para archivo (todos los niveles)
        log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
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


# Instancia global para importar directamente
logger = AppLogger()
