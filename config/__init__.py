from .manager import ConfigManager
from . import modules
from tools.dirs import get_data_path

config = ConfigManager(get_data_path() + "/config.json")