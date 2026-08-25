class DatabaseError(Exception):
    pass

class StockError(DatabaseError):
    pass

class CreditLimitExceededError(DatabaseError):
    pass

class InsufficientBalanceError(DatabaseError):
    pass