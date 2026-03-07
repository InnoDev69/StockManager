import threading
import time
from tools.logger import logger

class Scheduler:
    """Programador de tareas periódicas."""
    def __init__(self):
        self.tasks = []
        self.threads = []
        self._stop_event = threading.Event()

    def add_task(self, interval_seconds, target_func):
        """Agrega tarea periódica."""
        logger.info(f"Agregando tarea: {target_func.__name__} cada {interval_seconds} segundos")
        self.tasks.append((interval_seconds, target_func))

    def start(self):
        """Inicia el programador."""
        logger.info("Iniciando Scheduler")
        self._stop_event.clear()
        for interval, func in self.tasks:
            thread = self.run_periodically(interval, func)
            self.threads.append(thread)
        logger.info(f"{len(self.threads)} tarea(s) iniciada(s)")

    def run_periodically(self, interval_seconds, target_func):
        """Ejecuta función cada X segundos."""
        def wrapper():
            logger.debug(f"Hilo iniciado para: {target_func.__name__}")
            while not self._stop_event.is_set():
                try:
                    logger.debug(f"Ejecutando tarea periódica: {target_func.__name__}")
                    target_func()
                except Exception as e:
                    logger.error(f"Error en tarea periódica '{target_func.__name__}': {e}")
                # Espera interruptible
                self._stop_event.wait(timeout=interval_seconds)

        thread = threading.Thread(target=wrapper, daemon=True, name=target_func.__name__)
        thread.start()
        return thread

    def stop(self):
        """Detiene todas las tareas."""
        logger.info("Deteniendo Scheduler")
        self._stop_event.set()
        for thread in self.threads:
            thread.join(timeout=5)
        self.threads.clear()
        logger.info("Scheduler detenido")

SCHEDULER = Scheduler()