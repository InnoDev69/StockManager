import os
import sys
from bd.bdConector import BDConector
from dotenv import load_dotenv
from debug.logger import logger

load_dotenv()

def get_db_path():
    """
    Obtiene la ruta correcta para la base de datos según el entorno.
    
    - En desarrollo: usa DB_PATH del .env o ./bd/database.db
    - En producción (PyInstaller): crea la BD en un directorio escribible
    """
    if getattr(sys, 'frozen', False):
        app_dir = os.path.dirname(sys.executable)
        data_dir = os.path.join(app_dir, 'data')
        os.makedirs(data_dir, exist_ok=True)
        return os.path.join(data_dir, 'database.db')
    else:
        return os.getenv("DB_PATH", "./bd/database.db")

db = BDConector(db_path=get_db_path())
db.init_db()