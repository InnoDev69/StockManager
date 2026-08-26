from ..manager import ConfigManager

ConfigManager.register_defaults("telemetry", {
    "enabled": True,
    "endpoint": "https://telemetry-stockly.yamirnu15.workers.dev/",
})
