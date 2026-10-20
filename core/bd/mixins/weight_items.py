from miscellaneous.logger import logger
from miscellaneous.local_time import localDate

from core.bd.bdErrors import DatabaseError

class WeightItemsMixin:
    """
    Mixin para la gestión de items de peso en la base de datos.
    Proporciona métodos para agregar, eliminar y obtener items de peso.
    """
    def add_weight_item(self, name, weight, price, price_per_gram, description=None):
            """
            Crea un producto vendido por peso (ej: jamón, pan).
     
            Args:
                name (str): nombre del producto
                weight (float): peso de referencia en stock (si aplica)
                price (float): precio para 'price_per_gram' gramos
                price_per_gram (float): base de gramos para el precio (ej: 500)
                description (str|None)
     
            Returns:
                int: id del weight_item creado
            """
            with self._cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO weight_items (name, weight, price, price_per_gram, description)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (name, weight, price, price_per_gram, description),
                )
                return cur.lastrowid
        
    