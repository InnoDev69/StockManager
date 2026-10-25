# Documentación técnica de `scheduler.py`

## 1. Visión General del Módulo

Implementa un programador de tareas periódicas basado en hilos daemon y `threading.Event`. Cada tarea se ejecuta inmediatamente al iniciar su hilo y luego espera un intervalo interrumpible. Expone la instancia global `SCHEDULER`.

El patrón es un **Scheduler/Worker Registry**, con control global y por tarea.

## 2. Dependencias

### Biblioteca estándar

- `threading`: hilos y eventos de parada.
- `time`: importado, pero no utilizado en la implementación actual.

### Internas

- `miscellaneous.logger.logger`.

## 3. API Pública

```python
class Scheduler:
    def __init__(self) -> None: ...

    def add_task(self, interval_seconds: float, target_func: Callable[[], Any]) -> None: ...
    def start(self) -> None: ...
    def run_periodically(
        self,
        interval_seconds: float,
        target_func: Callable[[], Any],
        stop_event: threading.Event | None = None,
    ) -> threading.Thread: ...
    def stop(self) -> None: ...
    def reset_task(self, target_func: Callable[[], Any]) -> bool: ...
```

- `add_task`: agrega una función y su intervalo. No inicia el hilo.
- `start`: limpia controles anteriores y crea un hilo por tarea registrada.
- `run_periodically`: inicia y devuelve el hilo daemon.
- `stop`: señala todos los eventos y espera hasta cinco segundos por hilo.
- `reset_task`: detiene y vuelve a iniciar una tarea; devuelve `False` si no la encuentra.

Todas las operaciones devuelven `None`, salvo `reset_task`, que retorna `bool`. Las funciones objetivo no reciben argumentos; sus excepciones se registran y no detienen el worker.

### `SCHEDULER`

```python
SCHEDULER: Scheduler
```

## 4. Consideraciones de Ingeniería

- **Complejidad:** `start` y `stop` son `O(t)` para `t` tareas/hilos; `reset_task` es `O(t)` por la búsqueda en lista; cada ejecución de una tarea es `O(1)` para el scheduler más el coste de la función objetivo.
- **Concurrencia:** `tasks`, `threads` y `_task_controls` no tienen locks. Llamar simultáneamente a `start`, `stop`, `add_task` o `reset_task` puede producir estados inconsistentes. Debe protegerse el registro o documentarse que el ciclo de vida se controla desde un único hilo.
- **Semántica temporal:** la tarea se ejecuta inmediatamente y el intervalo se cuenta después de finalizarla. Una tarea lenta puede desplazar el periodo; para scheduling de reloj fijo se necesita un planificador distinto.
- **Parada:** `join(timeout=5)` no garantiza terminación; una función bloqueada puede continuar ejecutándose después de `stop`. Los hilos daemon no deben ejecutar operaciones críticas que requieran finalización garantizada.
- **Duplicados:** `_task_controls` usa la función como clave; registrar dos veces la misma función sobrescribe el control, aunque `tasks` conserva ambas entradas.
- **Errores:** las excepciones se absorben tras registrarse, lo que mantiene vivo el worker pero puede ocultar fallos persistentes. Conviene añadir métricas, backoff y límites de reintento.
- **Validación:** intervalos cero o negativos pueden crear un bucle de alta frecuencia. Deben rechazarse valores no positivos y validar que `target_func` sea invocable.
- **Configuración:** `time` está importado sin uso y puede eliminarse.

## 5. Ejemplo de Uso

```python
from miscellaneous.scheduler import Scheduler

scheduler = Scheduler()


def refresh_cache() -> None:
    print("Actualizando caché")


scheduler.add_task(60.0, refresh_cache)
scheduler.start()
# ... al apagar la aplicación:
scheduler.stop()
```
