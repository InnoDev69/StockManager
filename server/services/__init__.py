from .backup import BackupService
from server.bd.bdInstance import db
from .cache import CacheService

backup_service = BackupService(db=db)
cache_service = CacheService()

__all__ = ['backup_service', 'cache_service']