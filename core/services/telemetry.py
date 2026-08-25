import requests

class TelemetryService: # TODO: Finish this class to send telemetry data to the server
    def __init__(self, config):
        self.config = config

    def is_enabled(self):
        return self.config.get("telemetry.enabled", True)

    def get_endpoint(self):
        return self.config.get("telemetry.endpoint", "https://telemetry.stockmanager.app")
    
    def _get_logs(self):
        pass
        
    def send_logs(self, logs):
        if not self.is_enabled():
            return
        endpoint = self.get_endpoint()
        
        requests.post(endpoint, json=logs)