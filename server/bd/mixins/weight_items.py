from miscellaneous.logger import logger
from miscellaneous.local_time import localDate

from server.bd.bdErrors import DatabaseError

class WeightItemsMixin:
    """
    Mixin para la gestión de items de peso en la base de datos.
    Proporciona métodos para agregar, eliminar y obtener items de peso.
    """
    def add_weight_item(self, item_name: str, weight: float, price: float, price_per_gram: float, description: str = None):
        """
        Agrega un nuevo item de peso a la base de datos.
        
        :param item_name: Nombre del item.
        :param weight: Peso del item.
        :param price: Precio del item.
        :param price_per_gram: Precio por gramo del item.
        :param description: Descripción opcional del item.
        :raises DatabaseError: Si ocurre un error al interactuar con la base de datos.
        """
        try:
            with self.conn:
                cur = self.conn.cursor()
                cur.execute(
                    "INSERT INTO weight_items (name, weight, price, price_per_gram, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (item_name, weight, price, price_per_gram, description, localDate(), localDate())
                )
                logger.info(f"[DB] Item de peso '{item_name}' agregado exitosamente.")
        except Exception as e:
            logger.error(f"[DB] Error al agregar el item de peso '{item_name}': {e}")
            raise DatabaseError(f"Error al agregar el item de peso '{item_name}': {e}")
        
    