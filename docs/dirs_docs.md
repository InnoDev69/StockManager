# Documentación técnica de `dirs.py`

## 1. Visión General del Módulo

Centraliza la resolución y creación del directorio de datos de la aplicación. Diferencia ejecución de desarrollo y ejecución empaquetada con PyInstaller mediante `sys.frozen`, y permite obtener tanto el directorio base como una ruta de archivo relativa.

El patrón aplicado es un **resolver de infraestructura** con configuración por entorno. La carga de variables `.env` ocurre al importar el módulo.

## 2. Dependencias

### Biblioteca estándar

- `os`: rutas, variables de entorno y creación de directorios.
- `sys`: detección de ejecución congelada y plataforma.

### Terceros

- `python-dotenv.load_dotenv`: carga variables desde `.env`.

### Internas

- `miscellaneous.logger.logger`: trazas de resolución y creación de rutas.

## 3. API Pública

### `get_data_path`

```python
def get_data_path(archive: str | None = None) -> str:
    """Devuelve la ruta de datos según el entorno.

    Args:
        archive: Nombre relativo de archivo o subruta dentro del directorio
            de datos. Si es ``None``, devuelve el directorio base.

    Returns:
        Ruta absoluta o relativa configurada. Crea el directorio padre antes
        de devolverla.

    Raises:
        OSError: Si no puede crear el directorio.
        TypeError: Si ``archive`` no es compatible con operaciones de ruta.
    """
```

En desarrollo usa `DB_PATH` o `./data`. En modo congelado usa `%APPDATA%/StockManager/data` en Windows y `~/.stock_manager/data` en macOS/Linux.

## 4. Consideraciones de Ingeniería

- **Complejidad:** `O(1)` en operaciones de ruta, sin contar el coste del sistema de archivos para `os.makedirs`.
- **Rendimiento:** registra varios mensajes y comprueba el directorio en cada llamada. Para rutas de alta frecuencia puede usarse caché, manteniendo invalidación si cambia la configuración.
- **Seguridad:** `archive` debe tratarse como ruta no confiable si proviene de entrada externa. Sin validación, `../` puede escapar del directorio de datos. Aplicar `Path.resolve()` y comprobar que la ruta resultante permanece bajo la raíz permitida.
- **Configuración:** `os.path.join(None, ...)` puede fallar si `%APPDATA%` no está definido. Debe existir un fallback validado.
- **Concurrencia:** `exist_ok=True` hace idempotente la creación concurrente en condiciones normales, aunque los errores de permisos o carreras con un archivo del mismo nombre deben propagarse.
- **Casos límite:** un `archive` vacío se comporta como ausencia; subdirectorios intermedios se crean; una ruta absoluta puede reemplazar el prefijo de `data_dir` en `os.path.join`, lo que refuerza la necesidad de validación.
- **Portabilidad:** la rama no Windows agrupa macOS y Linux; conviene verificar convenciones de permisos y rutas XDG si la aplicación debe integrarse plenamente con cada plataforma.

## 5. Ejemplo de Uso

```python
from miscellaneous.dirs import get_data_path

base_path = get_data_path()
database_path = get_data_path("stock.db")
image_path = get_data_path("images/product.png")

print(base_path, database_path, image_path)
```
