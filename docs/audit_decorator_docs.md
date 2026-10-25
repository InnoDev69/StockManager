# Documentación técnica de `audit_decorator.py`

## 1. Visión General del Módulo

Proporciona un decorador para registrar automáticamente en la base de datos las acciones ejecutadas por endpoints Flask. Captura actor, IP, método, entidad, identificador, snapshots antes/después, descripción legible y estado de la operación.

El diseño combina **Decorator**, **lazy import** para evitar ciclos (`_get_db`) y tablas de traducción para desacoplar nombres internos de textos de auditoría. También contiene formateadores especializados para creaciones, ventas, eliminaciones y actualizaciones.

## 2. Dependencias

### Biblioteca estándar

- `datetime.datetime`: marca temporal de los inicios de sesión.
- `functools.wraps`: conserva metadatos de la función decorada.

### Terceros

- `flask.request`: método HTTP, JSON y cabeceras.
- `flask.session`: identidad del usuario autenticado.

### Internas

- `miscellaneous.logger.logger`.
- `core.bd.bdInstance.db`, importado de forma diferida; debe proporcionar `execute_query`, `log_audit`, `get_item_by_id` y `get_username_by_id`.

## 3. API Pública

### `audit_action`

```python
def audit_action(
    entity_type: str,
    action_name: str | None = None,
    id_param: str | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decora una función Flask y registra su resultado en auditoría.

    Args:
        entity_type: Tipo lógico de entidad, por ejemplo ``"user"``,
            ``"product"`` o ``"sale"``.
        action_name: Acción explícita. Si es ``None``, usa el método HTTP en
            minúsculas.
        id_param: Nombre del argumento que contiene el ID de la entidad.

    Returns:
        Un decorador que envuelve la función objetivo y conserva sus metadatos.

    Raises:
        Exception: Propaga la excepción de la función decorada después de
            intentar registrar el error.
    """
```

Ejemplo de firma de uso:

```python
@audit_action("product", "update", "product_id")
def update_product(product_id: int):
    ...
```

### `get_client_ip`

```python
def get_client_ip() -> str:
    """Obtiene la IP del cliente usando ``X-Forwarded-For`` o Flask.

    Returns:
        La primera IP de ``X-Forwarded-For``, la dirección remota o
        ``"Unknown"``.
    """
```

### Funciones auxiliares

```python
def _get_db() -> Any: ...
def _label(field: str) -> str: ...
def _entity_label(entity_type: str) -> str: ...
def _format_value(field: str, value: Any) -> str: ...
def _build_create_description(entity_type: str, data: dict[str, Any]) -> str: ...
def _build_sale_create_description(data: dict[str, Any]) -> str: ...
def _build_delete_description(
    entity_type: str,
    entity_id: Any,
    old_value: dict[str, Any] | None,
) -> str: ...
def _build_default_description(
    action: str,
    entity_type: str,
    entity_id: Any = None,
) -> str: ...
def _compare_changes(
    old_value: dict[str, Any] | None,
    new_value: dict[str, Any] | None,
) -> str: ...
def _get_entity_before(entity_type: str, entity_id: Any) -> dict[str, Any] | None: ...
```

Las funciones con prefijo `_` son detalles internos y no forman parte del contrato público. Las constantes `ENTITY_LABELS`, `FIELD_LABELS`, `ACTION_LABELS`, `_CURRENCY_FIELDS` y `_SKIP_ON_CREATE` configuran la presentación de auditoría.

## 4. Consideraciones de Ingeniería

- **Complejidad:** `_label`, `_entity_label` y `_format_value` son `O(1)` promedio. `_build_create_description` y `_compare_changes` son `O(n)` en la cantidad de campos. `_build_sale_create_description` es `O(s)` para `s` líneas de venta, con una consulta de producto por línea. `_get_entity_before` es `O(1)` respecto al número de entidades si existen índices por `id`; el coste físico depende de la base de datos.
- **Rendimiento:** cada actualización realiza snapshots y cada venta puede producir consultas N+1. Puede resolverse con una consulta por lote o incorporando nombres al payload transaccional.
- **Concurrencia:** el snapshot previo y la escritura posterior no forman una operación atómica con la mutación de negocio. Para auditoría estricta, deben ejecutarse dentro de la misma transacción o registrarse con versionado.
- **Seguridad de proxy:** confiar ciegamente en `X-Forwarded-For` permite falsificar la IP si la aplicación no está detrás de un proxy confiable. La cabecera debe aceptarse solo desde proxies configurados.
- **Privacidad:** aunque se omite `password` al crear, los datos arbitrarios del JSON pueden contener información sensible. Debe existir una política de allowlist/redacción para campos auditables.
- **Errores de auditoría:** en el bloque de excepción se vuelve a llamar a la base de datos. Si la BD está caída, el error original podría quedar acompañado por un segundo fallo; conviene aislar y registrar ese fallo sin ocultar la excepción original.
- **Respuestas Flask:** la detección del estado solo contempla tuplas simples (`response[1]`). Respuestas `Response` con código distinto de 200 pueden clasificarse incorrectamente.
- **Casos límite:** snapshots ausentes producen `"Cambios registrados (snapshot parcial)"`; una entidad desconocida usa su nombre capitalizado; una entidad inexistente se representa por ID. `request` y `session` requieren contexto Flask activo.
- **Reloj:** `datetime.now()` usa hora local del servidor y no zona horaria explícita. Para sistemas distribuidos se recomienda UTC con zona (`datetime.now(timezone.utc)`).

## 5. Ejemplo de Uso

```python
from flask import Flask, jsonify

from miscellaneous.audit_decorator import audit_action

app = Flask(__name__)
app.secret_key = "development-only-secret"


@app.post("/products/<int:product_id>")
@audit_action("product", "update", "product_id")
def update_product(product_id: int):
    # La mutación real debe ejecutarse mediante la capa de persistencia.
    return jsonify({"product_id": product_id, "updated": True}), 200
```

El endpoint debe ejecutarse con contexto Flask y con la instancia de base de datos configurada para que el registro sea persistido.
