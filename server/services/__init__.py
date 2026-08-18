from .backup import BackupService
from .cache import CacheService
from miscellaneous import get_data_path
import os

db_name = os.getenv("DB_NAME") or "stock.db"
backup_service = BackupService(db=get_data_path(db_name))
cache_service = CacheService()

all = ["backup_service", "cache_service"]