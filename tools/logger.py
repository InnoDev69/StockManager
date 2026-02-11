"""
Sistema centralizado de logging para toda la aplicación.

Este módulo implementa un logger singleton que escribe simultáneamente a consola
y archivo, con rotación diaria de logs y limpieza automática de archivos antiguos.
Facilita debugging, auditoría y diagnóstico de problemas en producción.
"""
import logging
import os
import sys
from datetime import datetime

def get_log_dir():
    """
    Determina el directorio apropiado para almacenar archivos de log.
    
    La ubicación varía según el entorno y sistema operativo para garantizar
    permisos de escritura y accesibilidad apropiada para el usuario.
    
    Returns:
        str: Ruta absoluta al directorio de logs
    
    Ubicaciones:
        - Desarrollo: ./logs (relativo a la raíz del proyecto)
        - Producción Windows: %APPDATA%/StockManager/logs
        - Producción Linux/Mac: ~/.stock_manager/logs
    
    Note:
        El directorio se crea automáticamente si no existe.
    """
    if getattr(sys, 'frozen', False):
        # Aplicación empaquetada con PyInstaller
        if sys.platform == "win32":
            base_dir = os.path.join(os.getenv("APPDATA"), "StockManager", "logs")
        else:  # macOS y Linux
            base_dir = os.path.join(os.path.expanduser("~"), ".stock_manager", "logs")
    else:
        # Modo desarrollo
        base_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
    
    return base_dir
    
class AppLogger:
    """
    Logger singleton con salida dual (consola + archivo) y rotación diaria.
    
    Implementa el patrón Singleton para garantizar una única instancia en toda
    la aplicación, evitando duplicación de logs y conflictos de handlers.
    
    Características:
        - Rotación diaria de archivos (un archivo por día)
        - Limpieza automática de logs antiguos (>3 días por defecto)
        - Nivel DEBUG en archivo, WARNING en consola (evita spam)
        - Formato consistente con timestamp y nivel
    
    Usage:
        >>> from tools.logger import logger
        >>> logger.info("Operación completada")
        >>> logger.error("Error crítico", exc_info=True)
    
    Attributes:
        _instance: Instancia singleton del logger
        _logger: Instancia interna de logging.Logger
    """
    
    _instance = None
    _logger = None
    
    def __new__(cls):
        """
        Implementación del patrón Singleton.
        
        Garantiza que solo exista una instancia de AppLogger en toda la aplicación,
        sin importar cuántas veces se importe o instancie.
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._setup_logger()
        return cls._instance
    
    def _cleanup_old_logs(self, days_to_keep=3):
        """
        Elimina archivos de log más antiguos que el número de días especificado.
        
        Previene el crecimiento indefinido del directorio de logs manteniendo
        solo los archivos recientes. Se ejecuta automáticamente vía scheduler.
        
        Args:
            days_to_keep (int): Número de días de logs a conservar (default: 3)
        
        Note:
            Solo elimina archivos con formato app_YYYYMMDD.log.
            Los errores de eliminación se registran como warnings pero no interrumpen.
        """
        log_dir = get_log_dir()
        if not os.path.exists(log_dir):
            return
        
        now = datetime.now()
        for filename in os.listdir(log_dir):
            if filename.startswith("app_") and filename.endswith(".log"):
                file_path = os.path.join(log_dir, filename)
                try:
                    timestamp_str = filename[4:-4]  # Extrae la fecha del nombre
                    file_date = datetime.strptime(timestamp_str, "%Y%m%d")
                    if (now - file_date).days > days_to_keep:
                        os.remove(file_path)
                        self._logger.info(f"Log antiguo eliminado: {filename}")
                except Exception as e:
                    self._logger.warning(f"No se pudo eliminar el log antiguo {filename}: {str(e)}")
    
    def _setup_logger(self):
        """
        Configura el logger con handlers de consola y archivo.
        
        Se ejecuta automáticamente al crear la primera instancia del logger.
        Configura formato, niveles y destinos de salida.
        
        Note:
            Verifica handlers existentes para evitar duplicación si se llama múltiples veces.
        """
        self._logger = logging.getLogger("StockManager")
        self._logger.setLevel(logging.DEBUG)  # Nivel global más bajo
        
        # Evita duplicar handlers si ya existen
        if self._logger.handlers:
            return
        
        # Formato consistente para todos los logs
        formatter = logging.Formatter(
            fmt="[%(asctime)s] %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        
        # Handler de consola: solo WARNING y superior para evitar spam
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.WARNING)
        console_handler.setFormatter(formatter)
        self._logger.addHandler(console_handler)
        
        # Handler de archivo: todo desde DEBUG, rotación diaria por nombre
        log_dir = get_log_dir()
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, f"app_{datetime.now().strftime('%Y%m%d')}.log")
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        self._logger.addHandler(file_handler)
    
    def error(self, message: str, exc_info: bool = False):
        """
        Registra un mensaje de error.
        
        Args:
            message (str): Descripción del error
            exc_info (bool): Si True, incluye el traceback completo de la excepción actual
        
        Example:
            >>> try:
            ...     risky_operation()
            ... except Exception:
            ...     logger.error("La operación falló", exc_info=True)
        """
        self._logger.error(message, exc_info=exc_info)
    
    def warning(self, message: str):
        """
        Registra un mensaje de advertencia.
        
        Args:
            message (str): Descripción de la advertencia
        
        Example:
            >>> logger.warning("Stock bajo detectado en 5 productos")
        """
        self._logger.warning(message)
    
    def info(self, message: str):
        """
        Registra un mensaje informativo.
        
        Args:
            message (str): Información sobre el estado de la aplicación
        
        Example:
            >>> logger.info("Servidor iniciado en puerto 5000")
        """
        self._logger.info(message)
    
    def debug(self, message: str):
        """
        Registra un mensaje de debug (solo visible en archivo).
        
        Args:
            message (str): Información detallada de debugging
        
        Note:
            Los mensajes debug NO aparecen en consola para evitar spam,
            pero quedan en el archivo de log para diagnóstico posterior.
        
        Example:
            >>> logger.debug(f"Query ejecutado: {query} con params {params}")
        """
        self._logger.debug(message)
    
    def exception(self, message: str):
        """
        Registra una excepción con traceback completo.
        
        Equivalente a error(message, exc_info=True) pero más semántico.
        Debe llamarse desde un bloque except para capturar el contexto correcto.
        
        Args:
            message (str): Descripción contextual de la excepción
        
        Example:
            >>> try:
            ...     process_data()
            ... except Exception:
            ...     logger.exception("Error procesando datos del CSV")
        """
        self._logger.exception(message)


# Instancia global del logger
# Usar esta instancia en toda la aplicación para logging consistente
logger = AppLogger()
