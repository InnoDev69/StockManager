"""
Instancia global de la base de datos.

Este módulo configura y expone la instancia singleton del conector de base de datos,
asegurando que la ruta de la BD sea correcta según el entorno (desarrollo vs producción).

El uso de una instancia global simplifica el acceso a la BD desde cualquier parte
de la aplicación sin necesidad de pasar el objeto como dependencia.

Note:
    Incluye correcciones específicas para AppImage en Linux, asegurando que
    la base de datos se almacene en un directorio escribible del usuario.
"""
import os
import sys
from bd.bdConector import BDConector
from dotenv import load_dotenv
from tools.logger import logger

load_dotenv()

def get_db_path():
    """
    Determina la ruta apropiada para el archivo de base de datos según el entorno.
    
    La función detecta si la aplicación está ejecutándose como binario empaquetado
    (PyInstaller/AppImage) o en modo desarrollo, y retorna una ruta escribible apropiada.
    
    Returns:
        str: Ruta absoluta al archivo database.db
    
    Comportamiento:
        - Desarrollo: Lee DB_PATH del .env o usa ./bd/database.db por defecto
        - Producción (Windows): %APPDATA%/StockManager/data/database.db
        - Producción (Linux/Mac): ~/.stock_manager/data/database.db
    
    Note:
        En producción, crea automáticamente los directorios necesarios si no existen.
        Esto evita errores de permisos en directorios de instalación de solo lectura,
        particularmente importante para AppImage donde el contenido es de solo lectura.
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

# Instancia global de base de datos
# Usar esta instancia en lugar de crear nuevas conexiones para mantener consistencia
db = BDConector(db_path=get_db_path())
db.init_db()