import os
import shutil
import time
from datetime import datetime

from miscellaneous import logger, SCHEDULER
from client.config import config

class BackupService:
    def __init__(self, db):
        self.db = db
        self.logger_name = "BACKUP_MODULE"
        if config.get("backup.auto_enabled"):
            self._start_service()
            logger.info(f"BackupService initialized with database: {self.db}", source=self.logger_name)
        else:
            logger.info("BackupService is disabled in configuration.", source=self.logger_name)

    def _start_backup_service(self):
        SCHEDULER.add_task(
            config.get("backup.frequency_days") * 86400,
            self._perform_backup
        )  # Schedule daily backups
        logger.info(
            f"Started backup service for {self.db} interval: {config.get('backup.frequency_days')}",
            source=self.logger_name
        )

    def _start_service(self):
        self._start_backup_service()

    def _perform_backup(self):
        backup_dir = config.get("backup.destination_path")
        if not backup_dir:
            logger.error(
                "Backup destination path is not configured.",
                source=self.logger_name,
            )
            return

        logger.info(f"Performing backup for {self.db} to {backup_dir}", source=self.logger_name)
        self.backup_database(backup_dir)
        self._cleanup_old_backups(backup_dir)

    def backup_database(self, backup_dir):
        """Copia el archivo de la base de datos a la carpeta indicada."""
        if not backup_dir:
            logger.error("Backup destination path is not configured.", source=self.logger_name)
            raise ValueError("backup_dir is required")

        os.makedirs(backup_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{os.path.splitext(os.path.basename(self.db))[0]}_{timestamp}.bak"
        dest_path = os.path.join(backup_dir, filename)

        try:
            shutil.copy2(self.db, dest_path)
            logger.info(f"Backup successfully saved to {dest_path}", source=self.logger_name)
            return dest_path
        except Exception as e:
            logger.error(f"Backup failed: {e}", source=self.logger_name)
            raise

    def restore_database(self, backup_path):
        """Restaura la base de datos desde un archivo de backup."""
        logger.info(f"Restoring database from {backup_path}", source=self.logger_name)

        if not os.path.exists(backup_path):
            logger.warning(f"Backup file not found: {backup_path}", source=self.logger_name)
            raise FileNotFoundError(backup_path)

        shutil.copy2(backup_path, self.db)
        logger.info(f"Database restored from {backup_path}", source=self.logger_name)

    def _cleanup_old_backups(self, backup_dir):
        """Elimina backups con más días de antigüedad que backup.retention_days."""
        retention_days = config.get("backup.retention_days")
        if not retention_days:
            return

        cutoff = time.time() - (retention_days * 86400)

        if not os.path.isdir(backup_dir):
            return

        for fname in os.listdir(backup_dir):
            if not fname.endswith(".bak"):
                continue

            fpath = os.path.join(backup_dir, fname)
            try:
                if os.path.getmtime(fpath) < cutoff:
                    os.remove(fpath)
                    logger.info(f"Deleted expired backup: {fpath}", source=self.logger_name)
            except Exception as e:
                logger.error(f"Failed to check/delete backup {fpath}: {e}", source=self.logger_name)