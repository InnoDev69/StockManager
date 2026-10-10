# Documentación técnica de `timmer.py`

## 1. Visión General del Módulo

Define un decorador que mide el tiempo de ejecución de una función usando un reloj monotónico de alta resolución. Solo mide y registra cuando el nivel interno del logger es `DEBUG`; en otros niveles ejecuta la función sin instrumentación adicional.

El patrón es **Decorator/Instrumentation Wrapper**, con `functools.wraps` para preservar metadatos.

## 2. Dependencias

### Biblioteca estándar

- `logging`: comparación del nivel de logging.
- `time`: `perf_counter` monotónico.
- `functools.wraps`: preservación de identidad documental.

### Internas

- `miscellaneous.logger.logger`.

## 3. API Pública

### `measure_time`

```python
from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")

def measure_time(func: Callable[..., T]) -> Callable[..., T]:
    """Decora una función para medir su duración en modo debug.

    Args:
        func: Función invocable a instrumentar.

    Returns:
        Wrapper con la misma semántica de retorno y excepciones que `func`.

    Raises:
        Exception: Propaga cualquier excepción producida por `func`.
    """
```

El wrapper acepta `*args` y `**kwargs`, devuelve exactamente el resultado de la función y no captura excepciones.

## 4. Consideraciones de Ingeniería

- **Complejidad:** añade `O(1)` de trabajo y memoria alrededor de la función; el coste dominante sigue siendo el de `func`.
- **Medición:** `perf_counter` es apropiado para duración transcurrida y no depende de cambios del reloj del sistema.
- **Rendimiento:** en modo debug añade dos lecturas de reloj, formateo y escritura de log; en funciones muy pequeñas puede distorsionar el resultado.
- **Concurrencia:** es seguro si `logger` se usa según las garantías de `logging`; las mediciones son locales a cada invocación y no comparten estado mutable.
- **Configuración:** consulta `logger._level`, un atributo privado. Sería más robusto exponer una propiedad o usar `logger.isEnabledFor(logging.DEBUG)`.
- **Excepciones:** si la función falla, no se registra duración ni mensaje de fallo. Puede añadirse `try/finally` si la telemetría requiere medir también errores.
- **Casos límite:** funciones async no se miden correctamente: el wrapper mediría la creación de la coroutine, no su ejecución. Para ellas debe existir un decorador `async def` separado.
- **Tipado:** el código actual carece de anotaciones; `ParamSpec` y `TypeVar` pueden conservar mejor la firma estática.

## 5. Ejemplo de Uso

```python
from miscellaneous.timmer import measure_time


@measure_time
def calculate_total(values: list[int]) -> int:
    return sum(values)


print(calculate_total([1, 2, 3]))
```
