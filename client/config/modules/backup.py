from ..manager import ConfigManager

ConfigManager.register_defaults("backup", {
    "auto_enabled": False,
    "frequency_days": 7,
    "retention_days": 5,
    "destination_type": "sync_folder",
    })

# Ejemplo de migración: si en el futuro renombrás retention_count -> retention_days
# ConfigManager.register_migration(2, lambda data: {
#     **data,
#     "backup": {**data["backup"], "retention_days": data["backup"].pop("retention_count", 5)}
# })