# API (Dev)

Base path: `/api`

This API is designed to be consumed by the Flask-served UI within the same app (session/cookies). It is not a public token-based API.

## Authentication

- Most endpoints require an active session.
- The auth guard is `require_auth()` and checks `session["user_id"]`.
- If there is no session, the API returns `401`.

Health check:
- `GET /api/health` does not require login.

## Roles

- Admin endpoints validate `session.get("role") == "admin"`.
- For label/value details ("Administrador" vs stored value), see [docs/en/SECURITY_ROLES.md](SECURITY_ROLES.md).

## Endpoints

### Health

- `GET /api/health`
  - Auth: no
  - Response: `{ "status": "Ok" }`

### Products

- `GET /api/products_all`
  - Auth: yes
  - Description: lists products with filters; includes disabled items.
  - Query params:
    - `search` (string, optional)
    - `view_mode` (`all` | `in_stock` | `out_of_stock`, optional)

- `GET /api/products`
  - Auth: yes
  - Description: lists active products (`status = 1`) with filters.
  - Query params:
    - `search` (string, optional)
    - `view_mode` (`all` | `in_stock` | `out_of_stock`, optional)

- `GET /api/products/<product_id>`
  - Auth: yes
  - Description: returns a product by id.
  - Responses:
    - `404` if not found

- `POST /api/products`
  - Auth: yes
  - Role: admin
  - JSON body (required fields):
    - `barcode` (string)
    - `name` (string)
    - `quantity` (int)
    - `min_quantity` (int)
    - `price` (float)
    - `description` (string, optional)
  - Response: `201` with `{ "message": "Producto creado exitosamente" }`

- `PUT /api/products/<product_id>`
  - Auth: yes
  - Role: admin
  - JSON body (partial): any of:
    - `name`, `description`, `quantity`, `min_quantity`, `price`, `status`

- `DELETE /api/products/<product_id>`
  - Auth: yes
  - Role: admin
  - Note: performs a “soft delete” by disabling the item (status=0).

### Dashboard

- `GET /api/stats`
  - Auth: yes
  - Description: aggregated dashboard stats.

### Sales

- `POST /api/sales`
  - Auth: yes
  - JSON body:
    - `barcode` (string)
    - `quantity` (int)
  - Responses:
    - `404` if product not found
    - `400` if insufficient stock

- `POST /api/sales/bulk`
  - Auth: yes
  - JSON body:
    - `items`: array of `{ "item_id": int, "quantity": int }`
  - Response: `{ ok, sale_id, items, total }`

- `GET /api/sales`
  - Auth: yes
  - Query params:
    - `from` (YYYY-MM-DD, optional)
    - `to` (YYYY-MM-DD, optional)

- `GET /api/sales/<sale_id>`
  - Auth: yes (directly checks `session["user_id"]`)
  - Note: returns an explicit `Content-Type: application/json`.

### Items (search/autocomplete)

- `GET /api/items`
  - Auth: yes
  - Query params:
    - `q` (string)
  - Response: array with up to 10 items.

### Metrics

- `GET /api/metrics`
  - Auth: yes
  - Query params:
    - `period` (int; e.g. 7, 30, 90, 365)
    - `from` (YYYY-MM-DD)
    - `to` (YYYY-MM-DD)

## Quick examples (dev)

Examples depend on a valid session (cookie). In dev, the simplest workflow is:

1. Start the app (`npm start`).
2. Log in via the UI.
3. Use DevTools → Network / Console to call endpoints from the browser context.

Example in browser console:

```js
fetch('/api/health').then(r => r.json())
```
