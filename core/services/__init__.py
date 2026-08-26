from .backup import BackupService
from .cache import CacheService
from miscellaneous import get_data_path
import os
from .permissions_service import PermissionsService
from .telemetry import TelemetryService

db_name = os.getenv("DB_NAME") or "stock.db"
backup_service = BackupService(db=get_data_path(db_name))
cache_service = CacheService()
permissions_service = PermissionsService()
telemetry_service = TelemetryService()

all = ["backup_service", "cache_service", "permissions_service", "telemetry_service"]