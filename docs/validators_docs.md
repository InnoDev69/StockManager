# Documentación técnica de `validators.py`

## 1. Visión General del Módulo

Define validación reutilizable para textos y números, además de validadores específicos para productos, usuarios y roles. Devuelve valores normalizados y lanza `ValidationError` con campo y mensaje cuando una entrada no es válida.

El diseño aplica **Template/Static Utility Methods**: `Validator` concentra primitivas y los validadores especializados las componen. La configuración de longitudes proviene de `Limits` y los nombres válidos de `ROLES`.

## 2. Dependencias

### Biblioteca estándar

- `re`: validación complementaria de emails.

### Internas

- `miscellaneous.limits.Limits`.
- `miscellaneous.roles.ROLES`.

No usa dependencias de terceros.

## 3. API Pública

### `ValidationError`

```python
class ValidationError(Exception):
    def __init__(self, field: str, message: str) -> None: ...
```

Representa un error de entrada y expone `field: str` y `message: str`.

### `Validator`

```python
class Validator:
    @staticmethod
    def validate_string(
        field: str,
        value: str | None,
        max_length: int,
        required: bool = True,
    ) -> str | None: ...

    @staticmethod
    def validate_number(
        field: str,
        value: object | None,
        min_val: float = 0,
        max_val: float | None = None,
        allow_float: bool = False,
        required: bool = True,
    ) -> int | float | None: ...
```

`validate_string` elimina espacios extremos y comprueba tipo, obligatoriedad y longitud. `validate_number` convierte a `int` o `float`, y comprueba los límites inclusivos. Ambas lanzan `ValidationError` ante errores.

### `ItemValidator`

```python
class ItemValidator:
    @staticmethod
    def validate(
        barrs_code: str | None,
        description: str | None,
        name: str | None,
        quantity: object | None,
        min_quantity: object | None,
        price: object | None,
        expiration_date: str | None,
        status: object | None,
    ) -> dict[str, object]: ...
```

Valida y devuelve las claves del producto: `barrs_code`, `description`, `name`, `quantity`, `min_quantity`, `price`, `expiration_date` y `status`.

### `UserValidator`

```python
class UserValidator:
    @staticmethod
    def validate_custom(**fields: object) -> dict[str, object]: ...
    @staticmethod
    def validate_email(email: object) -> str: ...
    @staticmethod
    def validate(
        username: object,
        password: object,
        email: object,
        role: str = ROLES.VENDOR,
    ) -> dict[str, object]: ...
```

`validate_custom` valida solo campos conocidos; `validate_email` comprueba longitud y un formato básico; `validate` valida el registro completo.

### `RoleValidator`

```python
class RoleValidator:
    namespaces: list[str]
    permissions: dict[str, str]

    @staticmethod
    def validate_name(name: str) -> str: ...
    @staticmethod
    def validate_permissions(permissions: object) -> str: ...
    @staticmethod
    def validate(name: str, permissions: object) -> dict[str, str]: ...
```

Valida el nombre contra `root`, `admin` y `vendedor`, y valida el texto de permisos.

Todos los métodos de validación pueden lanzar `ValidationError`; los métodos actuales también pueden lanzar `AttributeError` o `TypeError` si reciben valores incompatibles antes de que las comprobaciones de tipo se ejecuten.

## 4. Consideraciones de Ingeniería

- **Complejidad:** validaciones de texto y números son `O(n)` para la longitud del valor; diccionarios resultado son `O(k)` para `k` campos. El regex de email es lineal para entradas normales.
- **Bug de configuración:** `RoleValidator.validate_permissions` y `RoleValidator.validate` usan `Limits.ROLE_PERMISSIONS_MAX`, pero `limits.py` no define ese atributo. Es un `AttributeError` en tiempo de ejecución; debe añadirse el límite o cambiarse a una constante existente.
- **Bug de tipo:** `validate_string` declara conceptualmente `str`, pero retorna `None` cuando `required=False` y el valor es `None`; el contrato debe anotarse como `str | None` o normalizar a cadena vacía.
- **Conversión numérica:** `int(1.5)` trunca silenciosamente. Si se prohíben fracciones, debe rechazarse un `float` no entero antes de convertir. `float('nan')` también evade comparaciones de rango; debe rechazarse `NaN` e infinitos.
- **Dinero:** `price` se valida como `float`; para importes exactos conviene `Decimal` y cuantización explícita.
- **Email:** la expresión es deliberadamente básica y no garantiza entregabilidad. Además, la condición con `"@"` y `"."` puede aceptar formatos que el regex rechazaría o permitir caracteres no deseados. Usar una política clara y normalización de dominio.
- **Seguridad:** validar longitud no sustituye sanitización contextual, hashing de contraseñas ni autorización para asignar `role`. Nunca almacenar la contraseña devuelta en texto plano.
- **Concurrencia:** las clases no mantienen estado por instancia; son seguras mientras no se muten las listas/diccionarios de clase (`namespaces`, `permissions`).
- **Casos límite:** roles no-string provocan `AttributeError` en `.lower()`; claves desconocidas en `validate_custom` fallan; `barrs_code` conserva el nombre existente aunque parece un typo de `barcode`.

## 5. Ejemplo de Uso

```python
from miscellaneous.validators import ItemValidator, UserValidator, ValidationError

try:
    product = ItemValidator.validate(
        barrs_code="7791234567890",
        description="Café molido",
        name="Café",
        quantity=10,
        min_quantity=2,
        price="1250.50",
        expiration_date="2027-12-31",
        status=1,
    )
    user = UserValidator.validate(
        username="seller01",
        password="temporary-password",
        email="seller@example.com",
    )
except ValidationError as error:
    print(f"Campo inválido: {error.field}: {error.message}")
```
