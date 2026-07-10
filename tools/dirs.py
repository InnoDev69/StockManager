import os
import sys

from dotenv import load_dotenv

from tools.logger import logger

load_dotenv()

def get_data_path(archive=None):
    """
    Devuelve la ruta al directorio de datos, dependiendo del entorno.
    - En desarrollo: ./data
    - En producción (PyInstaller): un directorio específico para la app en el home del usuario
    
    Args:
        archive (str, optional): Nombre del archivo específico dentro del directorio de datos (ej: "stock.db"). Si se proporciona, se devuelve la ruta completa a ese archivo.
    """
    if getattr(sys, 'frozen', False):
        if sys.platform == "win32":  # Windows
            data_dir = os.path.join(os.getenv("APPDATA"), "StockManager", "data")
        else:  # macOS y Linux (incluyendo AppImage)
            data_dir = os.path.join(os.path.expanduser("~"), ".stock_manager", "data")
        os.makedirs(data_dir, exist_ok=True)
        if archive:
            return os.path.join(data_dir, archive)
        
        logger.info(f"Using data directory (production mode): {data_dir}", source="DIRS_MODULE")
        
        return data_dir
    else:
        path = os.getenv("DB_PATH", "./data")
        if archive:
            path = os.path.join(path, archive)
        dir = os.path.dirname(path)
        
        if dir:
            logger.info(f"Ensuring directory exists: {dir}", source="DIRS_MODULE")
            os.makedirs(dir, exist_ok=True)
        
        logger.info(f"Using path (dev mode): {path}", source="DIRS_MODULE")
        return path