import os
from bd.bdConector import BDConector
from dotenv import load_dotenv

load_dotenv()

db = BDConector(db_path=os.getenv("DB_PATH", "./bd/database.db"))
db.init_db()