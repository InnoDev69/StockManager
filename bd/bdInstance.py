from flask.cli import load_dotenv

from bd.bdConector import BDConector
from tools.dirs import get_data_path

import os

load_dotenv()

db = BDConector(db_path=get_data_path(archive=os.getenv("DB_NAME")))
db.init_db()