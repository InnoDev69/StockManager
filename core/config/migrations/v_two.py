from ..manager import ConfigManager

@ConfigManager.migration(2)
def migrate_to_v2(data):
    """Migración a la versión 2: se cambia de destination_type a destination_path"""
    backup_config = data.get("backup", {})
    destination_type = backup_config.pop("destination_type", "sync_folder")
    backup_config["destination_path"] = destination_type
    data["backup"] = backup_config
    return data