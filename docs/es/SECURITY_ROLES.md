# Roles y permisos

Este documento describe cómo se representan y aplican los roles en el proyecto (UI + backend).

## Roles existentes

En la práctica hay **dos perfiles**:

- **Vendedor**: puede operar ventas y ver información general.
- **Administrador**: puede gestionar catálogo (CRUD) e importar productos.

### Valores reales del rol

El rol se guarda en:

- Base de datos: columna `users.role`.
- Sesión Flask: `session["role"]` (se carga al iniciar sesión).

Importante:
- Los checks de permisos del backend comparan contra el literal **`"admin"`**.
- En UI el formulario de registro ofrece:
  - `Vendedor` (value `"Vendedor"`)
  - `Administrador` (value `"admin"`)

Conclusión: **"Administrador" en la interfaz equivale a `role == "admin"` en backend**.

## Dónde se aplican permisos

### Backend (aplicación Flask: rutas HTML)

En `main.py` hay rutas protegidas por rol, por ejemplo:

- Crear producto (`/products/new`): requiere login y `session.get("role") == "admin"`.
- Importación CSV (`/import` y `/import/confirm`): requiere admin.

Si no cumple, se redirige al dashboard.

### Backend (API REST)

En `api/API.py`:

- Autenticación: `require_auth()` exige `session["user_id"]` para la mayoría de endpoints.
- Autorización admin (bloquea con `403`):
  - `POST /api/products`
  - `PUT /api/products/<id>`
  - `DELETE /api/products/<id>` (baja lógica vía `status=0`)

## UI (no es seguridad)

Las plantillas usan el rol para ocultar/mostrar secciones (por ejemplo, botones “admin-only”).

Esto es solo **presentación**; la seguridad real debe depender de los checks del servidor (`main.py` y `api/API.py`).

## Notas y consistencia

- En el dashboard se usa `session.get("role", "Vendedor")` para renderizar; si por algún motivo `session["role"]` falta, la UI asumirá “Vendedor”.
- En `register_post()` el rol por defecto es `"user"`, pero el formulario HTML normalmente envía `"Vendedor"` o `"admin"`.
  - Recomendación: tratar cualquier valor distinto de `"admin"` como “no admin” (Vendedor).

