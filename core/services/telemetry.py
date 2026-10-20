import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock, Thread

import requests
from core.config import config
from miscellaneous.logger import logger, get_log_files
from miscellaneous.scheduler import SCHEDULER

from miscellaneous.dirs import get_data_path

SEND_INTERVAL = timedelta(hours=24)   # mínimo entre envíos
CHECK_INTERVAL_SECONDS = 3600         # cada cuánto se revisa si toca enviar
MAX_DAYS_BACK = 7                     # tope de días de logs por envío
LEVELS = ("WARNING", "ERROR", "CRITICAL")

# get_data_path devuelve un str: se convierte a Path para poder usar with_suffix, etc.
STATE_PATH = Path(get_data_path("telemetry_state.json"))

_LOG_DATE_RE = re.compile(r"app_(\d{8})\.log$")

LOGGER_NAME = "TelemetryService"

class TelemetryService:
    def __init__(self):
        self.enabled = config.get("telemetry.enabled", default=False)
        self.endpoint = config.get("telemetry.endpoint", default="https://telemetry.stockmanager.app")
        self._lock = Lock()

        if self.enabled:
            SCHEDULER.add_task(CHECK_INTERVAL_SECONDS, self.service)
            Thread(target=self.service, name="telemetry-startup", daemon=True).start()
            logger.info("Servicio de telemetría habilitado.", source=LOGGER_NAME)

    def get_endpoint(self):
        return self.endpoint

    def _load_last_sent(self):
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                return datetime.fromisoformat(json.load(f)["last_sent"])
        except FileNotFoundError:
            return None
        except Exception as e:
            logger.error(f"No se pudo leer el estado de telemetría: {e}", source=LOGGER_NAME)
            return None

    def _save_last_sent(self, moment):
        try:
            tmp_path = STATE_PATH.with_suffix(".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump({"last_sent": moment.isoformat()}, f)
            os.replace(tmp_path, STATE_PATH)  # escritura atómica
        except Exception as e:
            logger.error(f"No se pudo guardar el estado de telemetría: {e}", source=LOGGER_NAME)

    def _is_due(self, last_sent):
        return last_sent is None or datetime.now() - last_sent >= SEND_INTERVAL

    # ------------------------------------------------------------------
    # Logs
    # ------------------------------------------------------------------

    def _get_log(self, since=None):
        """
        Devuelve las líneas WARNING/ERROR/CRITICAL de los logs desde la fecha
        `since` (inclusive) hasta hoy, con un tope de MAX_DAYS_BACK días.
        Si `since` es None, solo se toma el log de hoy.
        """
        today = datetime.now().date()
        earliest = today - timedelta(days=MAX_DAYS_BACK)
        start = max(since.date(), earliest) if since else today

        lines = []
        try:
            log_files = sorted(get_log_files())
        except Exception as e:
            logger.error(f"Error obteniendo los archivos de log: {e}", source=LOGGER_NAME)
            return []

        for log_file in log_files:
            match = _LOG_DATE_RE.search(os.path.basename(log_file))
            if not match:
                continue
            try:
                file_date = datetime.strptime(match.group(1), "%Y%m%d").date()
            except ValueError:
                continue
            if not (start <= file_date <= today):
                continue
            try:
                with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                    lines.extend(
                        line.strip()
                        for line in f
                        if any(level in line for level in LEVELS)
                    )
            except Exception as e:
                logger.error(f"Error reading log file {log_file}: {e}", source=LOGGER_NAME)
        return lines
    
    def _get_unrecognized_count(self):
        """
        Devuelve el número de palabras no reconocidas por el bot desde el último envío.
        """
        from core.api.chat_api import UNRECOGNIZED_PATH
        try:
            with open(UNRECOGNIZED_PATH, "r", encoding="utf-8") as f:
                return len(f.readlines())
        except FileNotFoundError:
            return 0

    # ------------------------------------------------------------------
    # Envío
    # ------------------------------------------------------------------

    def send_logs(self, logs):
        """Devuelve True si el servidor aceptó los datos."""
        if not self.enabled:
            return False

        data = {
            "user": config.get("app.uuid", default="unknown"),
            "timestamp": datetime.now().isoformat(),
            "logs": logs,
            "bot_unrecognized_words": self._get_unrecognized_count(),
            "os": sys.platform,
        }

        try:
            response = requests.post(self.get_endpoint(), json=data, timeout=5)
        except requests.RequestException as e:
            logger.error(f"Error sending telemetry data: {e}", source=LOGGER_NAME)
            return False

        if response.status_code == 200:
            logger.info("Telemetría enviada con éxito.", source=LOGGER_NAME)
            return True

        logger.error(f"Telemetría rechazada por el servidor (HTTP {response.status_code}).", source=LOGGER_NAME)
        return False

    def service(self):
        if not self._lock.acquire(blocking=False):
            return
        try:
            last_sent = self._load_last_sent()
            if not self._is_due(last_sent):
                return

            logs = self._get_log(since=last_sent)
            if self.send_logs(logs):
                self._save_last_sent(datetime.now())
        except Exception:
            logger.exception("Error inesperado en el servicio de telemetría.", source=LOGGER_NAME)
        finally:
            self._lock.release()