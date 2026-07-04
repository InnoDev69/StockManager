import threading
import time
from tools.logger import logger

class Scheduler:
    """Programador de tareas periódicas."""
    def __init__(self):
        self.tasks = []
        self.threads = []
        self._logger_name = "Scheduler"
        self._stop_event = threading.Event()

    def add_task(self, interval_seconds, target_func):
        """Agrega tarea periódica."""
        logger.info(f"[{self._logger_name}] Agregando tarea: {target_func.__name__} cada {interval_seconds} segundos")
        self.tasks.append((interval_seconds, target_func))

    def start(self):
        """Inicia el programador."""
        logger.info(f"[{self._logger_name}] Iniciando Scheduler")
        self._stop_event.clear()
        for interval, func in self.tasks:
            thread = self.run_periodically(interval, func)
            self.threads.append(thread)
        logger.info(f"[{self._logger_name}] {len(self.threads)} tarea(s) iniciada(s)")

    def run_periodically(self, interval_seconds, target_func):
        """Ejecuta función cada X segundos."""
        def wrapper():
            logger.debug(f"[{self._logger_name}] Hilo iniciado para: {target_func.__name__}")
            while not self._stop_event.is_set():
                try:
                    logger.debug(f"[{self._logger_name}] Ejecutando tarea periódica: {target_func.__name__}")
                    target_func()
                except Exception as e:
                    logger.error(f"[{self._logger_name}] Error en tarea periódica '{target_func.__name__}': {e}")
                # Espera interruptible
                self._stop_event.wait(timeout=interval_seconds)

        thread = threading.Thread(target=wrapper, daemon=True, name=target_func.__name__)
        thread.start()
        return thread

    def stop(self):
        """Detiene todas las tareas."""
        logger.info(f"[{self._logger_name}] Deteniendo Scheduler")
        self._stop_event.set()
        for thread in self.threads:
            thread.join(timeout=5)
        self.threads.clear()
        logger.info(f"[{self._logger_name}] Scheduler detenido")
        
    def reset_task(self, target_func):
        """Reinicia una tarea específica."""
        logger.info(f"[{self._logger_name}] Reiniciando tarea: {target_func.__name__}")
        self.stop()
        self.tasks = [(interval, func) for interval, func in self.tasks if func != target_func]
        self.start()

SCHEDULER = Scheduler()