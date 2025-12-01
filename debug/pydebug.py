import logging

class DebugLogger:
    def __init__(self, name='debug_logger'):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        
        # Colors
        self.colors = {
            'DEBUG': '\033[94m',    # Blue
            'INFO': '\033[92m',     # Green
            'WARNING': '\033[93m',  # Yellow
            'ERROR': '\033[91m',    # Red
            'CRITICAL': '\033[95m', # Magenta
            'ENDC': '\033[0m',      # Reset to default
        }

    def log_debug(self, message):
        self.logger.debug(f"{self.colors['DEBUG']}{message}{self.colors['ENDC']}")

    def log_info(self, message):
        self.logger.info(f"{self.colors['INFO']}{message}{self.colors['ENDC']}")
    def log_warning(self, message):
        self.logger.warning(f"{self.colors['WARNING']}{message}{self.colors['ENDC']}")

    def log_error(self, message):
        self.logger.error(f"{self.colors['ERROR']}{message}{self.colors['ENDC']}")

    def log_critical(self, message):
        self.logger.critical(f"{self.colors['CRITICAL']}{message}{self.colors['ENDC']}")