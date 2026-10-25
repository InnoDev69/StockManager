# Documentación técnica de `limits.py`

## 1. Visión General del Módulo

Define los límites máximos y mínimos usados por validadores de productos, usuarios y fechas. `Limits` es una clase contenedora de constantes de clase; no mantiene estado por instancia ni requiere construcción.

El patrón es **Constants/Configuration Object**. Los límites de año se calculan dinámicamente al importar el módulo, relativos al año actual del reloj del sistema.

## 2. Dependencias

### Biblioteca estándar

- `datetime`: cálculo del año mínimo y máximo del calendario.

### Terceros e internas

- No tiene dependencias de terceros ni dependencias internas.

## 3. API Pública

### `Limits`

```python
class Limits:
    """Límites de caracteres y valores para validación."""

    ITEM_NAME_MAX: int
    ITEM_DESCRIPTION_MAX: int
    ITEM_BARCODE_MAX: int
    ITEM_QUANTITY_MAX: int
    ITEM_MIN_QUANTITY_MAX: int
    ITEM_PRICE_MAX: float
    ITEM_ATRIBUTE_NAME_MAX: int
    ITEM_ATRIBUTE_VALUE_MAX: int
    ITEM_EXPIRATION_DATE_MAX: int
    USER_USERNAME_MAX: int
    USER_PASSWORD_MAX: int
    USER_EMAIL_MAX: int
    USER_ROLE_MAX: int
    USER_CODE_MAX: int
    CALENDAR_YEAR_MAX: int
    CALENDAR_YEAR_MIN: int
```

No expone métodos públicos. Las constantes principales son límites de nombre, descripción, código de barras, cantidades, precio, atributos, credenciales y años válidos.

## 4. Consideraciones de Ingeniería

- **Complejidad:** acceso a cualquier constante es `O(1)` y no existe algoritmo crítico.
- **Rendimiento:** coste de importación constante; el cálculo de año requiere una sola lectura del reloj.
- **Semántica temporal:** `CALENDAR_YEAR_MIN` y `CALENDAR_YEAR_MAX` quedan congelados hasta recargar el proceso. Para procesos de larga duración o pruebas alrededor de Año Nuevo, conviene calcularlos mediante una función o inyectar el reloj.
- **Validación numérica:** `ITEM_PRICE_MAX` es `float`, lo que puede introducir errores binarios para dinero. Las reglas de persistencia deberían usar `Decimal` o enteros en unidades mínimas.
- **Mantenibilidad:** `ITEM_ATRIBUTE_*` parece contener un error ortográfico en `ATTRIBUTE`; cambiar el nombre puede romper consumidores y requiere una transición compatible.
- **Seguridad:** los límites de longitud no sustituyen validación de formato, normalización, autorización ni consultas parametrizadas.
- **Casos límite:** el máximo de expiración está documentado como longitud de `YYYY-MM-DD`, pero la longitud no garantiza una fecha válida. Deben validarse calendario y rango por separado.

## 5. Ejemplo de Uso

```python
from miscellaneous.limits import Limits

product_name = "Café molido"
if len(product_name) <= Limits.ITEM_NAME_MAX:
    print("Nombre válido")
else:
    print("Nombre demasiado largo")

print(Limits.CALENDAR_YEAR_MIN, Limits.CALENDAR_YEAR_MAX)
```
