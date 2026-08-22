import os
import sys

from dotenv import load_dotenv

from .logger import logger

load_dotenv()

def get_data_path(archive=None):
    """
    Devuelve la ruta al directorio de datos, dependiendo del entorno.
    - En desarrollo: ./data
    - En producción (PyInstaller): un directorio específico para la app en el home del usuario
    Args:
        archive (str, optional): Nombre del archivo específico dentro del directorio de datos
            (ej: "stock.db" o "images/foo.png"). Si se proporciona, se devuelve la ruta
            completa a ese archivo, creando cualquier subdirectorio intermedio necesario.
    """
    if getattr(sys, 'frozen', False):
        if sys.platform == "win32":  # Windows
            data_dir = os.path.join(os.getenv("APPDATA"), "StockManager", "data")
        else:  # macOS y Linux (incluyendo AppImage)
            data_dir = os.path.join(os.path.expanduser("~"), ".stock_manager", "data")
        logger.info(f"Using data directory (production mode): {data_dir}", source="DIRS_MODULE")
    else:
        data_dir = os.getenv("DB_PATH", "./data")
        logger.info(f"Using path (dev mode): {data_dir}", source="DIRS_MODULE")

    path = os.path.join(data_dir, archive) if archive else data_dir

    target_dir = os.path.dirname(path) if archive else path
    if target_dir:
        logger.info(f"Ensuring directory exists: {target_dir}", source="DIRS_MODULE")
        os.makedirs(target_dir, exist_ok=True)

    return path