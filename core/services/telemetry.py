from datetime import datetime
import sys

import requests
from core.config import config
from miscellaneous.logger import logger, get_log_files
from miscellaneous.scheduler import SCHEDULER

class TelemetryService:
    def __init__(self):
        self.enabled = config.get("telemetry.enabled", default=False)
        self.endpoint = config.get("telemetry.endpoint", default="https://telemetry.stockmanager.app")
        if self.enabled:
            SCHEDULER.add_task(86400, self.service)  # Ejecuta cada dia (24 horas)
            logger.info("Servicio de telemetría habilitado.", source="TelemetryService")
    
    def get_endpoint(self):
        return self.endpoint
    
    def _get_log(self):
        """Obtiene las líneas WARNING/ERROR/CRITICAL del log del día actual. Retorna [] si no hay o falla la lectura."""
        for log_file in get_log_files():
            if log_file.endswith(f"app_{datetime.now().strftime('%Y%m%d')}.log"):
                try:
                    with open(log_file, 'r') as f:
                        return [
                            line.strip()
                            for line in f
                            if "WARNING" in line or "ERROR" in line or "CRITICAL" in line
                        ]
                except Exception as e:
                    logger.error(f"Error reading log file {log_file}: {e}")
                    return []
        return []
        
    def send_logs(self, logs):
        if not self.enabled:
            return
        endpoint = self.get_endpoint()
        
        data = {
            "user": config.get("app.uuid", default="unknown"),
            "timestamp": datetime.now().isoformat(),
            "logs": logs,
            "os": sys.platform,
        }
        
        try:
            response = requests.post(endpoint, json=data, timeout=5)
        
            if response.status_code == 200:
                logger.info("Telemetría enviada con éxito.")
        except requests.RequestException as e:
            logger.error(f"Error sending telemetry data: {e}")
    
    def service(self):
        logs = self._get_log()
        self.send_logs(logs)