class DatabaseError(Exception):
    """Error genérico de la capa de base de datos."""
    pass


class StockError(DatabaseError, ValueError):
    """
    Error de stock. También es ValueError: es una regla de negocio incumplida
    (datos inválidos para la operación pedida), no una falla de la base. Así los
    'except ValueError' de la API lo tratan como un 400 en vez de un 500.
    """
    pass


class CreditLimitExceededError(DatabaseError):
    pass


class InsufficientBalanceError(DatabaseError):
    pass


class InsufficientStockError(StockError):
    """
    Stock insuficiente. Lleva los datos del problema para que la API pueda
    informarlos sin volver a consultar la base:
        product   -- nombre del producto
        requested -- cantidad (o gramos) pedidos
        available -- cantidad (o gramos) disponibles
    """

    def __init__(self, message="", product=None, requested=None, available=None):
        super().__init__(message)
        self.product = product
        self.requested = requested
        self.available = available


class ItemNotFoundError(DatabaseError, ValueError):
    """Un producto referenciado en una venta no existe. Es un dato inválido del pedido (400)."""
    pass


class ProductUnavailableError(DatabaseError, ValueError):
    """Un producto existe pero está deshabilitado y no se puede vender (400)."""
    pass