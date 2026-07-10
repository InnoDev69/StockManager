import threading
import time
from tools.logger import logger

class Scheduler:
    """Programador de tareas periódicas."""
    def __init__(self):
        self.tasks = []
        self.threads = []
        self._task_controls = {}
        self._logger_name = "Scheduler"
        self._stop_event = threading.Event()

    def add_task(self, interval_seconds, target_func):
        """Agrega tarea periódica."""
        logger.info(
            f"Agregando tarea: {target_func.__name__} cada {interval_seconds} segundos",
            source=self._logger_name,
        )
        self.tasks.append((interval_seconds, target_func))

    def start(self):
        """Inicia el programador."""
        logger.info("Iniciando Scheduler", source=self._logger_name)
        self._stop_event.clear()
        self.threads.clear()
        self._task_controls.clear()
        for interval, func in self.tasks:
            self._start_task(interval, func)
        logger.info(f"{len(self.threads)} tarea(s) iniciada(s)", source=self._logger_name)

    def _start_task(self, interval_seconds, target_func):
        task_stop_event = threading.Event()
        thread = self.run_periodically(interval_seconds, target_func, task_stop_event)
        self._task_controls[target_func] = {
            "interval": interval_seconds,
            "stop_event": task_stop_event,
            "thread": thread,
        }
        self.threads.append(thread)
        return thread

    def run_periodically(self, interval_seconds, target_func, stop_event=None):
        """Ejecuta función cada X segundos."""
        task_stop_event = stop_event or self._stop_event

        def wrapper():
            logger.debug(f"Hilo iniciado para: {target_func.__name__}", source=self._logger_name)
            while not self._stop_event.is_set() and not task_stop_event.is_set():
                try:
                    logger.debug(
                        f"Ejecutando tarea periódica: {target_func.__name__}",
                        source=self._logger_name,
                    )
                    target_func()
                except Exception as e:
                    logger.error(
                        f"Error en tarea periódica '{target_func.__name__}': {e}",
                        source=self._logger_name,
                    )
                # Espera interruptible
                task_stop_event.wait(timeout=interval_seconds)

        thread = threading.Thread(target=wrapper, daemon=True, name=target_func.__name__)
        thread.start()
        return thread

    def stop(self):
        """Detiene todas las tareas."""
        logger.info("Deteniendo Scheduler", source=self._logger_name)
        self._stop_event.set()
        for control in self._task_controls.values():
            control["stop_event"].set()
        for thread in self.threads:
            thread.join(timeout=5)
        self.threads.clear()
        self._task_controls.clear()
        logger.info("Scheduler detenido", source=self._logger_name)
        
    def reset_task(self, target_func):
        """Reinicia una tarea específica."""
        logger.info(f"Reiniciando tarea: {target_func.__name__}", source=self._logger_name)

        control = self._task_controls.get(target_func)
        interval_seconds = None

        if control:
            interval_seconds = control["interval"]
            control["stop_event"].set()
            control["thread"].join(timeout=5)
            self.threads = [thread for thread in self.threads if thread is not control["thread"]]
            self._task_controls.pop(target_func, None)
        else:
            for interval, func in self.tasks:
                if func == target_func:
                    interval_seconds = interval
                    break

        if interval_seconds is None:
            logger.warning(
                f"No se encontró la tarea a reiniciar: {target_func.__name__}",
                source=self._logger_name,
            )
            return False

        self._start_task(interval_seconds, target_func)
        return True

SCHEDULER = Scheduler()