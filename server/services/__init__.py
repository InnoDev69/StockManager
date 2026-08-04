from .backup import BackupService
from miscellaneous import get_data_path
from .cache import CacheService

backup_service = BackupService(db=get_data_path("stock.db"))
cache_service = CacheService()

__all__ = ['backup_service', 'cache_service']