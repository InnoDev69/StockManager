from flask.cli import load_dotenv

from server.bd.bdConector import BDConector
from miscellaneous import get_data_path

import os

load_dotenv()

db_name = os.getenv("DB_NAME") or "stock.db"
db = BDConector(db_path=get_data_path(archive=db_name))
db.init_db()