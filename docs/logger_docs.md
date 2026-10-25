# Documentación técnica de `logger.py`

## 1. Visión General del Módulo

Implementa el logging centralizado de StockManager, con salida a consola y a un archivo diario. Selecciona el directorio según desarrollo o bundle PyInstaller, mantiene tres días de retención mediante un método interno y expone una instancia global `logger`.

El patrón principal es **Singleton de módulo** mediante `AppLogger.__new__`, junto con configuración de handlers de la biblioteca `logging`.

## 2. Dependencias

### Biblioteca estándar

- `logging`: logger, handlers, niveles y formateo.
- `os`: rutas, directorios, archivos y variables de entorno.
- `sys`: plataforma y detección de PyInstaller.
- `datetime.datetime`: nombres de archivos y retención.

### Terceros e internas

- No tiene dependencias de terceros ni internas directas.

## 3. API Pública

```python
def get_current_log_file() -> str | None: ...
def get_log_files() -> list[str]: ...
def get_log_dir() -> str: ...
```

### `get_current_log_file`

Devuelve el archivo diario si existe; en caso contrario retorna `None`.

### `get_log_files`

Devuelve rutas de archivos cuyo nombre sigue `app_*.log`. Si el directorio no existe, devuelve una lista vacía.

### `get_log_dir`

Devuelve `./logs` relativo al proyecto en desarrollo o el directorio de usuario en modo congelado.

### `AppLogger`

```python
class AppLogger:
    def error(self, message: str, exc_info: bool = False, source: str | None = None) -> None: ...
    def warning(self, message: str, source: str | None = None) -> None: ...
    def info(self, message: str, source: str | None = None) -> None: ...
    def debug(self, message: str, source: str | None = None) -> None: ...
    def exception(self, message: str, source: str | None = None) -> None: ...
    def critical(self, message: str, source: str | None = None) -> None: ...
```

Cada método registra un mensaje y devuelve `None`. `error` puede añadir traceback mediante `exc_info=True`; `exception` siempre delega el traceback contextual del logger. `logger: AppLogger` es la instancia global recomendada.

## 4. Consideraciones de Ingeniería

- **Complejidad:** `get_current_log_file` es `O(1)`; `get_log_files` y `_cleanup_old_logs` son `O(n)` en archivos del directorio; escribir un mensaje es `O(m)` en su tamaño.
- **Rendimiento:** el handler de archivo realiza I/O síncrono por mensaje. En cargas elevadas conviene `QueueHandler`/`QueueListener` o logging estructurado centralizado.
- **Concurrencia:** `logging` protege handlers, pero el Singleton tiene inicialización manual. Los procesos separados pueden competir por el mismo archivo y la rotación diaria no está automatizada durante un proceso que cruza medianoche.
- **Retención:** `_cleanup_old_logs` no se invoca desde `_setup_logger`, por lo que los logs antiguos no se eliminan automáticamente salvo llamada externa.
- **Robustez:** `APPDATA` ausente puede generar rutas inválidas en Windows. Errores al crear el directorio o abrir el archivo pueden impedir importar el paquete completo.
- **Seguridad:** los mensajes pueden incluir secretos o datos personales. Debe aplicarse redacción, control de permisos del directorio y límites de tamaño.
- **Filtrado:** la salida de consola en modo congelado usa `WARNING`; el archivo conserva el nivel configurado. La decisión del nivel ocurre al importar, por lo que cambios posteriores de entorno no se reflejan.
- **Casos límite:** `get_log_files` no ordena ni valida que los candidatos sean archivos regulares; `get_current_log_file` depende de la fecha local del sistema.

## 5. Ejemplo de Uso

```python
from miscellaneous.logger import get_current_log_file, logger

logger.info("Aplicación iniciada", source="STARTUP")
try:
    raise ValueError("configuración inválida")
except ValueError:
    logger.exception("No se pudo cargar la configuración", source="STARTUP")

print(get_current_log_file())
```
