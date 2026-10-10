from threading import Thread, Event, RLock

from miscellaneous import logger

LOGGER_NAME = "SERVICE_MANAGER"

class Service:
    def __init__(self, name, function):
        """
        function: callable que recibe (stop_event, *args, **kwargs) y debe
        terminar cuando stop_event.is_set() sea True.
        """
        self.name = name
        self.function = function
        self._stop_event = Event()
        self._thread = None
        self._lock = RLock()

    @property
    def is_running(self):
        return self._thread is not None and self._thread.is_alive()

    def _run(self, *args, **kwargs):
        try:
            self.function(self._stop_event, *args, **kwargs)
        except Exception:
            logger.exception(f"Service '{self.name}' crashed.", source=LOGGER_NAME)
        finally:
            logger.info(f"Service '{self.name}' finished.", source=LOGGER_NAME)

    def start(self, *args, **kwargs):
        with self._lock:
            if self.is_running:
                raise RuntimeError(f"Service '{self.name}' is already running.")
            self._stop_event.clear()
            logger.info(f"Starting service '{self.name}'.", source=LOGGER_NAME)
            self._thread = Thread(
                target=self._run,
                args=args,
                kwargs=kwargs,
                name=f"service-{self.name}",
                daemon=True,
            )
            self._thread.start()
            return self._thread

    def stop(self, timeout=5):
        with self._lock:
            if not self.is_running:
                logger.info(f"Service '{self.name}' is not running.", source=LOGGER_NAME)
                return True
            logger.info(f"Stopping service '{self.name}'.", source=LOGGER_NAME)
            self._stop_event.set()
            thread = self._thread

        thread.join(timeout)
        if thread.is_alive():
            logger.warning(
                f"Service '{self.name}' did not stop within {timeout}s.", source=LOGGER_NAME
            )
            return False
        return True


class ServiceManager:
    def __init__(self):
        self.services = {}
        self._lock = RLock()

    def _get(self, service_name):
        with self._lock:
            if service_name not in self.services:
                raise ValueError(f"Service '{service_name}' is not registered.", source=LOGGER_NAME)
            return self.services[service_name]

    def register_service(self, service):
        with self._lock:
            if service.name in self.services:
                raise ValueError(f"Service '{service.name}' is already registered.", source=LOGGER_NAME)
            self.services[service.name] = service
        logger.info(f"Service '{service.name}' registered.", source=LOGGER_NAME)

    def start_service(self, service_name, *args, **kwargs):
        logger.info(f"Starting service '{service_name}'.", source=LOGGER_NAME)
        return self._get(service_name).start(*args, **kwargs)

    def stop_service(self, service_name, timeout=5):
        logger.info(f"Stopping service '{service_name}'.", source=LOGGER_NAME)
        return self._get(service_name).stop(timeout)

    def is_running(self, service_name):
        return self._get(service_name).is_running

    def stop_all(self, timeout=5):
        logger.info("Stopping all services.", source=LOGGER_NAME)
        with self._lock:
            services = list(self.services.values())
        for service in services:
            logger.debug(f"Stopping service '{service.name}'.", source=LOGGER_NAME)
            service.stop(timeout)
            
    def restart_all(self, timeout=5):
        logger.info("Restarting all services.", source=LOGGER_NAME)
        with self._lock:
            services = list(self.services.values())
        for service in services:
            logger.debug(f"Stopping service '{service.name}' for restart.", source=LOGGER_NAME)
            service.stop(timeout)
        for service in services:
            service.start()
            
SERVICE_MANAGER = ServiceManager()