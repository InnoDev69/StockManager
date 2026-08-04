from .manager import ConfigManager
from ..config import modules
from miscellaneous import get_data_path

config = ConfigManager(get_data_path() + "/config.json")