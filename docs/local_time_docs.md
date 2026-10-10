# Documentación técnica de `local_time.py`

## 1. Visión General del Módulo

Proporciona una función para obtener la fecha y hora actual de Buenos Aires con formato textual estable. La zona horaria se construye una vez al importar el módulo y se reutiliza en cada llamada.

El patrón es un **Clock Adapter**: encapsula la biblioteca temporal y expone el formato requerido por el resto de la aplicación.

## 2. Dependencias

### Biblioteca estándar

- `datetime.datetime`: obtiene la hora actual y la formatea.

### Terceros

- `pytz`: resolución de la zona horaria `America/Argentina/Buenos_Aires`.

## 3. API Pública

### `localDate`

```python
def localDate() -> str:
    """Devuelve la fecha y hora actual de Buenos Aires.

    Returns:
        Texto en formato ``YYYY-MM-DD HH:MM:SS``.

    Raises:
        pytz.UnknownTimeZoneError: Si la zona configurada no existe en la
            base de datos de zonas horarias instalada.
    """
```

### `ZONA`

```python
ZONA: pytz.tzinfo.BaseTzInfo
```

Representa la zona `America/Argentina/Buenos_Aires`.

## 4. Consideraciones de Ingeniería

- **Complejidad:** `localDate` es `O(1)` y produce una cadena de longitud fija.
- **Rendimiento:** la resolución de zona ocurre al importar; las llamadas posteriores solo consultan el reloj y formatean.
- **Consistencia:** devuelve texto sin información explícita de zona ni offset. Para APIs, persistencia y sistemas distribuidos es preferible guardar `datetime` consciente de zona o UTC y formatear en la capa de presentación.
- **Pruebas:** depende directamente del reloj global, por lo que las pruebas pueden ser no deterministas. Conviene inyectar un reloj o encapsular la obtención de `now`.
- **Concurrencia:** `pytz` puede reutilizarse de forma segura para esta operación; no se modifica el objeto global.
- **Casos límite:** el cambio de fecha cerca de medianoche depende del instante exacto; el formato no contiene milisegundos ni offset. `pytz` es compatible con el patrón usado porque no se localiza un `datetime` ingenuo manualmente.

## 5. Ejemplo de Uso

```python
from miscellaneous.local_time import localDate

created_at = localDate()
print(f"Registro creado en Buenos Aires: {created_at}")
```
