# Documentación técnica de `permissions.py`

## 1. Visión General del Módulo

Define identificadores constantes de permisos para ventas, productos, usuarios, configuración, crédito, métricas y herramientas de depuración.

El diseño es un **Namespace de constantes**. `PERMS` no instancia estado ni implementa autorización; solo evita strings dispersos y typos en políticas y decoradores.

## 2. Dependencias

No tiene dependencias de biblioteca estándar, terceros ni módulos internos.

## 3. API Pública

```python
class PERMS:
    SALES_CREATE: str
    SALES_EDIT: str
    SALES_VIEW_ALL: str
    PRODUCTS_MANAGE: str
    PRODUCTS_VIEW: str
    BARCODE_MANAGE: str
    USERS_MANAGE: str
    USERS_CHANGE_ROLE: str
    SETTINGS_MANAGE: str
    DEBUG_PANEL: str
    CREDIT_MANAGE: str
    CREDIT_ADJUST: str
    METRICS_VIEW: str
```

Cada atributo es una cadena estable. La clase no expone funciones ni métodos y no declara `Args`, `Returns` o `Raises` propios.

## 4. Consideraciones de Ingeniería

- **Complejidad:** acceso a una constante es `O(1)`.
- **Seguridad:** estos nombres no conceden permisos por sí mismos. Toda ruta protegida debe verificar identidad, alcance y permiso en el servidor, nunca confiar en el cliente.
- **Mantenibilidad:** cambiar un valor rompe datos persistidos, sesiones o configuración de roles; los cambios requieren migración o alias temporal.
- **Tipado:** un `Enum` o `Literal` podría ofrecer validación estática, aunque la clase actual es compatible con código existente y serialización simple.
- **Casos límite:** no hay permiso explícito para todas las áreas posibles; una política debe definir el comportamiento por defecto como denegar.

## 5. Ejemplo de Uso

```python
from miscellaneous.permissions import PERMS

required_permission = PERMS.PRODUCTS_MANAGE
user_permissions = {PERMS.PRODUCTS_VIEW, PERMS.PRODUCTS_MANAGE}

if required_permission in user_permissions:
    print("Operación autorizada")
```
