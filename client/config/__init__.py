from .manager import ConfigManager
from ..config import modules
from miscellaneous import get_data_path
from .import migrations #importa todo solo para disparar la ejecucion 

config = ConfigManager(get_data_path() + "/config.json")