class DatabaseError(Exception):
    pass

class StockError(DatabaseError):
    pass