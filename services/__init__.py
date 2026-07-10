from .backup import BackupService
from tools.dirs import get_data_path

backup_service = BackupService(db=get_data_path("stock.db"))

__all__ = ['backup_service']