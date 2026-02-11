# bd/bdInstance.py - Versión corregida para AppImage
import os
import sys
from bd.bdConector import BDConector
from dotenv import load_dotenv
from tools.logger import logger

load_dotenv()

def get_db_path():
    """
    Obtiene la ruta correcta para la base de datos según el entorno.
    
    - En desarrollo: usa DB_PATH del .env o ./bd/database.db
    - En producción (PyInstaller): crea la BD en un directorio escribible del usuario
    """
    if getattr(sys, 'frozen', False):
        appimage_path = os.environ.get('APPIMAGE')
        
        if sys.platform == "win32":  # Windows
            data_dir = os.path.join(os.getenv("APPDATA"), "StockManager", "data")
        else:  # macOS y Linux (incluyendo AppImage)
            data_dir = os.path.join(os.path.expanduser("~"), ".stock_manager", "data")
        
        os.makedirs(data_dir, exist_ok=True)
        db_path = os.path.join(data_dir, 'database.db')
        logger.info(f"Using database path (frozen mode): {db_path}")
        return db_path
    else:
        # Modo desarrollo
        db_path = os.getenv("DB_PATH", "./bd/database.db")
        logger.info(f"Using database path (dev mode): {db_path}")
        return db_path

db = BDConector(db_path=get_db_path())
db.init_db()