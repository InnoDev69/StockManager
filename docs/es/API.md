# API (Dev)

Base path: `/api`

Esta API está pensada para ser consumida por la UI servida por Flask dentro de la misma app (sesión/cookies). No es una API pública con tokens.

## Autenticación

- La mayoría de endpoints requieren sesión activa.
- El guard de autenticación es `require_auth()` y valida `session["user_id"]`.
- Si no hay sesión, responde `401`.

Health check:
- `GET /api/health` no requiere login.

## Roles

- Endpoints de administración validan `session.get("role") == "admin"`.
- Para detalles de cómo se guardan roles (labels vs valores), ver [docs/es/SECURITY_ROLES.md](SECURITY_ROLES.md).

## Endpoints

### Health

- `GET /api/health`
  - Auth: no
  - Response: `{ "status": "Ok" }`

### Productos

- `GET /api/products_all`
  - Auth: sí
  - Descripción: lista productos con filtros; incluye deshabilitados.
  - Query params:
    - `search` (string, opcional)
    - `view_mode` (`all` | `in_stock` | `out_of_stock`, opcional)

- `GET /api/products`
  - Auth: sí
  - Descripción: lista productos activos (`status = 1`) con filtros.
  - Query params:
    - `search` (string, opcional)
    - `view_mode` (`all` | `in_stock` | `out_of_stock`, opcional)

- `GET /api/products/<product_id>`
  - Auth: sí
  - Descripción: obtiene un producto por id.
  - Responses:
    - `404` si no existe

- `POST /api/products`
  - Auth: sí
  - Rol: admin
  - Body JSON (campos requeridos):
    - `barcode` (string)
    - `name` (string)
    - `quantity` (int)
    - `min_quantity` (int)
    - `price` (float)
    - `description` (string, opcional)
  - Response: `201` con `{ "message": "Producto creado exitosamente" }`

- `PUT /api/products/<product_id>`
  - Auth: sí
  - Rol: admin
  - Body JSON (parcial): cualquiera de:
    - `name`, `description`, `quantity`, `min_quantity`, `price`, `status`

- `DELETE /api/products/<product_id>`
  - Auth: sí
  - Rol: admin
  - Nota: hace “soft delete” deshabilitando el item (status=0).

### Dashboard

- `GET /api/stats`
  - Auth: sí
  - Descripción: stats agregadas para dashboard.

### Ventas

- `POST /api/sales`
  - Auth: sí
  - Body JSON:
    - `barcode` (string)
    - `quantity` (int)
  - Responses:
    - `404` si el producto no existe
    - `400` si stock insuficiente

- `POST /api/sales/bulk`
  - Auth: sí
  - Body JSON:
    - `items`: array de `{ "item_id": int, "quantity": int }`
  - Respuesta: `{ ok, sale_id, items, total }`

- `GET /api/sales`
  - Auth: sí
  - Query params:
    - `from` (YYYY-MM-DD, opcional)
    - `to` (YYYY-MM-DD, opcional)

- `GET /api/sales/<sale_id>`
  - Auth: sí (valida directamente `session["user_id"]`)
  - Nota: retorna `Content-Type: application/json` explícito.

### Items (búsqueda/autocomplete)

- `GET /api/items`
  - Auth: sí
  - Query params:
    - `q` (string)
  - Respuesta: array con hasta 10 items.

### Métricas

- `GET /api/metrics`
  - Auth: sí
  - Query params:
    - `period` (int; ej. 7, 30, 90, 365)
    - `from` (YYYY-MM-DD)
    - `to` (YYYY-MM-DD)

## Ejemplos rápidos (dev)

Los ejemplos dependen de tener una sesión válida (cookie). En dev, lo más práctico es:

1. Arrancar la app (`npm start`).
2. Loguearte en la UI.
3. Usar DevTools → Network / Console para probar endpoints desde el contexto del navegador.

Ejemplo en consola del navegador:

```js
fetch('/api/health').then(r => r.json())
```
