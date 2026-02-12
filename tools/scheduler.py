import threading
import time
from tools.logger import logger

class Scheduler:
    """Programador de tareas periódicas."""
    def __init__(self):
        self.tasks = []

    def add_task(self, interval_seconds, target_func):
        """Agrega tarea periódica."""
        logger.info(f"Agregando tarea: {target_func.__name__} cada {interval_seconds} segundos")
        self.tasks.append((interval_seconds, target_func))

    def start(self):
        """Inicia el programador."""
        logger.info("Iniciando Scheduler")
        for interval, func in self.tasks:
            self.run_periodically(interval, func)

    def run_periodically(self, interval_seconds, target_func):
        """Ejecuta función cada X segundos."""
        def wrapper():
            while True:
                time.sleep(interval_seconds)
                try:
                    logger.debug(f"Ejecutando tarea periódica: {target_func.__name__}")
                    target_func()
                except Exception as e:
                    logger.error(f"Error en tarea periódica: {e}")
        
        thread = threading.Thread(target=wrapper, daemon=True)
        thread.start()
        
SCHEDULER = Scheduler()