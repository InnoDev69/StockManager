# Documentación técnica de `roles.py`

## 1. Visión General del Módulo

Define los identificadores de roles reconocidos por la aplicación: administrador, vendedor y root.

El patrón es un **Namespace de constantes**. El módulo no implementa autenticación ni autorización; únicamente centraliza valores para evitar literales inconsistentes.

## 2. Dependencias

No tiene dependencias de biblioteca estándar, terceros ni módulos internos.

## 3. API Pública

```python
class ROLES:
    ADMIN: str
    VENDOR: str
    ROOT: str
```

Valores actuales: `"admin"`, `"vendedor"` y `"root"`. No existen funciones, argumentos, retornos ni excepciones propios.

## 4. Consideraciones de Ingeniería

- **Complejidad:** acceso a una constante es `O(1)`.
- **Seguridad:** `ROOT` representa un privilegio elevado y debe verificarse en backend con controles estrictos, auditoría y mínimo privilegio.
- **Mantenibilidad:** los valores se almacenan probablemente en sesiones o base de datos; cambiar una cadena requiere migración o compatibilidad de lectura.
- **Casos límite:** no hay rol desconocido ni jerarquía declarada. El sistema de autorización debe denegar valores no reconocidos y definir explícitamente si los roles son excluyentes o acumulables.
- **Tipado:** `Enum` o `Literal["admin", "vendedor", "root"]` mejorarían la detección estática sin cambiar la semántica externa si se introduce gradualmente.

## 5. Ejemplo de Uso

```python
from miscellaneous.roles import ROLES

current_role = ROLES.VENDOR
if current_role == ROLES.ADMIN:
    print("Puede administrar el sistema")
else:
    print("Aplicar permisos de vendedor")
```
