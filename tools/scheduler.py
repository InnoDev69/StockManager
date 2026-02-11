"""
Programador de tareas periódicas para operaciones en segundo plano.

Este módulo implementa un scheduler simple basado en threading para ejecutar
tareas de mantenimiento y limpieza en intervalos regulares (ej: limpieza de logs,
backups automáticos, sincronización de datos).
"""
import threading
import time
from tools.logger import logger

class Scheduler:
    """
    Programador de tareas periódicas ejecutadas en threads daemon.
    
    Permite registrar funciones que se ejecutarán automáticamente en intervalos
    definidos sin bloquear el thread principal de la aplicación.
    
    Attributes:
        tasks (list): Lista de tuplas (intervalo_segundos, función) a ejecutar
    
    Example:
        >>> scheduler = Scheduler()
        >>> scheduler.add_task(3600, cleanup_old_logs)  # cada hora
        >>> scheduler.start()
    
    Note:
        Los threads son daemon, por lo que se terminarán automáticamente
        cuando el programa principal finalice.
    """
    def __init__(self):
        """Inicializa un scheduler vacío sin tareas."""
        self.tasks = []

    def add_task(self, interval_seconds, target_func):
        """
        Registra una tarea para ejecución periódica.
        
        Args:
            interval_seconds (int): Tiempo entre ejecuciones en segundos
            target_func (callable): Función a ejecutar (sin argumentos)
        
        Example:
            >>> scheduler.add_task(86400, db.backup)  # backup diario
        
        Note:
            Las tareas no comienzan hasta llamar a start().
        """
        logger.info(f"Agregando tarea: {target_func.__name__} cada {interval_seconds} segundos")
        self.tasks.append((interval_seconds, target_func))

    def start(self):
        """
        Inicia la ejecución de todas las tareas registradas.
        
        Cada tarea se ejecuta en su propio thread daemon. Los threads no
        se detienen hasta que el proceso principal termina.
        
        Note:
            Esta función retorna inmediatamente, las tareas corren en background.
        """
        logger.info("Iniciando Scheduler")
        for interval, func in self.tasks:
            self.run_periodically(interval, func)

    def run_periodically(self, interval_seconds, target_func):
        """
        Ejecuta una función repetidamente con el intervalo especificado.
        
        Args:
            interval_seconds (int): Tiempo de espera entre ejecuciones
            target_func (callable): Función a ejecutar
        
        Note:
            Esta función crea un thread daemon que loop infinitamente.
            Los errores en target_func se loggean pero no detienen el scheduler.
        """
        def wrapper():
            while True:
                time.sleep(interval_seconds)
                try:
                    logger.debug(f"Ejecutando tarea periódica: {target_func.__name__}")
                    target_func()
                except Exception as e:
                    logger.error(f"Error en tarea periódica {target_func.__name__}: {e}", exc_info=True)
        
        thread = threading.Thread(target=wrapper, daemon=True, name=f"Scheduler-{target_func.__name__}")
        thread.start()

# Instancia global del scheduler
SCHEDULER = Scheduler()