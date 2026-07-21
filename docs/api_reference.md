# API Reference

This document describes the HTTP layer of StockManager: authentication, authorization, audit logging, error handling, and the main blueprints exposed by the application.

The goal is not just to list routes, but to explain how the API behaves in practice so another developer can extend it without breaking the existing flow.

## 1. How the API Is Structured

The application is organized around Flask blueprints. Each blueprint owns a domain:

- `users_api`: authentication, registration, user administration, password reset
- `products_api`: inventory and product management
- `sales_api`: sales registration and sale history
- `metrics_api`: dashboard and analytics data
- `notifications_api`: in-app notifications and SSE streaming
- `applications_api`: user application review workflow
- `audit_api`: audit log queries
- `changelog_api`: changelog retrieval
- `debug_bp`: privileged debug endpoints

This separation matters because the routes are not just HTTP handlers. They are the boundary between the web layer and the database/service layer. If a route mutates state, it should usually also be protected by authentication, role checks, and audit logging.

## 2. Authentication and Authorization

The project uses session-based authentication, not JWT.

### 2.1 Session model

After a successful login, the session stores at least:

- `session["user_id"]`
- `session["username"]`
- `session["role"]`

All subsequent protected requests rely on that session state.

### 2.2 `require_role()` decorator

The decorator in `api/auth_utils.py` is the unified access gate.

Behavior:

- Without roles, it only verifies that the user is logged in
- With roles, it also verifies that `session["role"]` is allowed
- For browser requests, failures return HTML templates
- For API requests, failures return JSON responses

### 2.3 API vs HTML response mode

The helper `_is_api_request()` decides whether to return JSON or HTML based on:

- URLs starting with `/api/`
- The `X-Requested-With: XMLHttpRequest` header
- The request `Accept` header, when JSON is the preferred format

This is a practical design choice: the same auth layer can support both template-rendered pages and programmatic clients.

### 2.4 Example

```python
@require_auth
def protected_view():
    return jsonify({"ok": True})
```

If the session is missing, the request gets a `401` for API calls or a login page for HTML calls.

## 3. Error Handling Strategy

The file `api/error_handlers.py` wraps database errors into user-friendly HTTP responses.

### 3.1 Main ideas

- `DatabaseError` becomes a domain-level database failure
- `sqlite3.IntegrityError` is translated into conflict or bad-request responses
- `sqlite3.OperationalError` is treated as an infrastructure error
- Any unexpected exception becomes a `500`

### 3.2 Why this matters

The UI should not see raw SQLite exceptions. Instead, it should receive a meaningful message such as:

- duplicate value -> `409 Conflict`
- invalid foreign key -> `400 Bad Request`
- generic DB failure -> `500 Internal Server Error`

### 3.3 Example usage

```python
try:
    db.add_user(...)
except DatabaseError as e:
    return handle_db_error(e, "create_user")
```

## 4. Audit Logging

The project uses `tools/audit_decorator.py` to automatically record important user actions.

### 4.1 What the decorator does

`audit_action(entity_type, action_name=None, id_param=None)` intercepts the request, captures the actor, and records a before/after snapshot when relevant.

It is used mainly for:

- creating entities
- updating entities
- deleting entities
- password and login events

### 4.2 What gets stored

The audit layer can store:

- actor user ID
- action name
- entity type
- entity ID
- previous value snapshot
- new value snapshot
- human-readable description
- client IP
- status

### 4.3 Why this is useful

This gives you traceability without polluting route code with manual audit boilerplate. In other words, the route stays focused on business logic, while audit instrumentation stays centralized.

### 4.4 Example

```python
@products_api.route("/products", methods=["POST"])
@require_role(ROLES.ADMIN, ROLES.ROOT)
@audit_action("product", "create")
def create_product():
    ...
```

## 5. Blueprint Reference

## 5.1 Applications Blueprint

File: `api/applications_api.py`

This blueprint manages the approval workflow for new user registrations.

### Routes

#### `GET /applications`

Returns pending applications with pagination.

Access:

- authenticated users with `ADMIN` or `ROOT`

Query params:

- `page`: page number, default `1`
- `limit`: page size, default `10`

Example response:

```json
{
  "data": [
    {
      "id": 12,
      "username": "maria",
      "email": "maria@example.com",
      "created_at": "2026-07-20 14:02:11"
    }
  ],
  "page": 1,
  "pages": 3,
  "total": 24
}
```

#### `POST /applications/<user_id>/approve`

Marks the application as accepted and activates the account.

Important behavior:

- sets `application = 'accepted'`
- sets `status = 1`

Example request:

```bash
curl -X POST /applications/12/approve
```

#### `POST /applications/<user_id>/reject`

Marks the application as rejected.

Example request:

```bash
curl -X POST /applications/12/reject
```

### Developer note

This flow is intentionally narrow. Approval is not a generic user update; it is a business action with its own audit trail.

## 5.2 Audit Blueprint

File: `api/audit_api.py`

This blueprint exposes the audit log for administrators and root users.

### Routes

#### `GET /user/<user_id>`

Returns the audit history for a specific user.

Rules:

- a user can view their own history
- `ROOT` can view any user history

Query params:

- `action`
- `from`
- `to`
- `limit`
- `offset`

Example response:

```json
{
  "total": 2,
  "records": [
    {
      "id": 15,
      "user_id": 3,
      "username": "admin",
      "action": "CREATE",
      "entity_type": "product",
      "entity_id": 8,
      "description": "Nuevo Producto creado",
      "timestamp": "2026-07-21T10:15:00",
      "status": "success"
    }
  ]
}
```

#### `GET /all`

Returns the full audit log.

Access:

- `ROOT` only

#### `GET /entity/<entity_type>/<entity_id>`

Returns the change trail for a specific entity.

Example:

```bash
GET /entity/product/8
```

## 5.3 Debug Blueprint

File: `api/debug_api.py`

This blueprint is privileged and intended for diagnostic use. It is restricted to `ROOT`.

### Routes

#### `POST /debug/log`

Receives client-side logs from JavaScript and mirrors them to the server log.

Example body:

```json
{
  "level": "error",
  "message": "Failed to render chart",
  "context": {"screen": "dashboard"}
}
```

#### `GET /debug/logs`

Returns the most recent log lines from the active log file.

#### `POST /debug/command`

Executes Python code on the server inside a restricted builtins dictionary.

Important:

- this is highly privileged
- it is only suitable for controlled internal environments
- it should never be exposed publicly without strong additional safeguards

Example body:

```json
{
  "code": "print(db.get_count(\"SELECT COUNT(*) FROM users\"))"
}
```

## 5.4 Changelog Blueprint

File: `api/changelog_api.py`

### Route

#### `GET /changelog`

Returns the latest changelog content fetched by `services.changelog_service.fetch_changelog()`.

Typical use:

- display release notes in the UI
- surface recent changes without opening documentation files manually

## 5.5 Notifications Blueprint

File: `api/notifications_api.py`

This blueprint handles notification CRUD plus a real-time SSE stream.

### Routes

#### `GET /notifications/unread`

Returns unread notifications and the unread counter for the current user.

Example response:

```json
{
  "notifications": [
    {
      "id": 9,
      "title": "Stock bajo",
      "message": "El producto Café Premium tiene stock bajo.",
      "type": "warning",
      "action_url": "/products/8",
      "created_at": "2026-07-21 09:30:00"
    }
  ],
  "unread_count": 1
}
```

#### `GET /notifications/all`

Returns all notifications with pagination.

#### `POST /notifications/<notification_id>/read`

Marks a notification as read.

#### `POST /notifications/read-all`

Marks all notifications as read for the current user.

#### `POST /notifications/create`

Creates a new notification for a target user.

Access:

- `ADMIN` or `ROOT`

Example body:

```json
{
  "user_id": 3,
  "title": "Stock bajo",
  "message": "El producto Café Premium está por agotarse",
  "type": "warning",
  "action_url": "/products/8"
}
```

#### `DELETE /notifications/<notification_id>/delete`

Deletes a notification.

### SSE stream

#### `GET /notifications/stream`

This endpoint returns `text/event-stream` and continuously pushes updates to the client.

Behavior:

- sends an initial `init` event with unread notifications and count
- waits for backend notification triggers
- emits `update` events when the unread state changes
- sends heartbeat comments to keep the connection alive

Why SSE is used here:

- it is lighter than websockets for one-way server-to-client updates
- it works well for notification counters and live inbox refreshes

## 5.6 Products Blueprint

File: `api/products_api.py`

This is the inventory surface of the application. It handles product retrieval, creation, update, barcode lookup, and bulk maintenance operations.

### Key routes described in the codebase

The file includes endpoints for:

- listing products with pagination and filters
- reading one product by ID
- creating products
- updating and deleting products
- activating products again
- bulk price and stock updates
- fetching external product metadata by barcode

### Behavioral notes

- Search and sorting are whitelisted to avoid SQL injection via `ORDER BY`
- Most list endpoints return normalized dictionaries rather than raw tuples
- Product creation and updates are wrapped with validation and audit events
- The code supports stock and visibility states separately

### Example list request

```bash
GET /products?search=cafe&view_mode=in_stock&sort=name&order=asc&page=1&limit=24
```

### Example product response

```json
{
  "id": 8,
  "barcode": "PRD0008",
  "name": "Café Premium",
  "description": "Bolsa de 1kg",
  "stock": 12,
  "min_stock": 5,
  "price": 9.99,
  "status": 1,
  "expiration_date": "2026-12-31"
}
```

### Practical interpretation

Treat this blueprint as the authoritative API for inventory operations. If a route changes stock, it should validate input, update the database atomically when needed, and record the action when the user performed a meaningful business operation.

## 5.7 Sales Blueprint

File: `api/sales_api.py`

This blueprint is responsible for turning inventory items into sales records.

### Routes

#### `POST /sales`

Registers a single-item sale.

Request body:

```json
{
  "barcode": "PRD0008",
  "quantity": 2,
  "payment_method": "Efectivo"
}
```

Operational flow:

1. Resolve the product from its barcode
2. Validate that there is enough stock
3. Create the sale row
4. Create the detail row
5. Deduct inventory
6. Return a success payload with totals

#### `POST /sales/bulk`

Registers a sale with multiple products.

Request body:

```json
{
  "items": [
    {"item_id": 8, "quantity": 2},
    {"item_id": 11, "quantity": 1}
  ],
  "payment_method": "Tarjeta"
}
```

This is the preferred route when the sale contains more than one product because the line items are first-class data in `details`.

#### `GET /sales`

Lists sales with filters such as date range, product name, vendor, page, and limit.

#### `GET /sales/<sale_id>`

Returns the full details of a single sale.

#### `GET /sales/<sale_id>/edit`

Returns sale data prepared for editing.

#### `PUT /sales/<sale_id>`

Updates an existing sale.

### Example response

```json
{
  "id": 41,
  "date": "2026-07-21 10:20:00",
  "vendedor": "admin",
  "vendor_id": 3,
  "payment_method": "Tarjeta",
  "products": [
    {
      "name": "Café Premium",
      "quantity": 2,
      "price": 9.99
    }
  ],
  "total": 19.98
}
```

### Important sales invariant

Sales are not just records. They are inventory mutations. If a sale succeeds, stock must be updated consistently. If one step fails, the transaction should fail as a whole.

## 5.8 Settings Blueprint

File: `api/settings_api.py`

This blueprint exposes application settings and profile actions.

### Routes

#### `PUT /settings/profile`

Updates the current user email.

#### `PUT /settings/password`

Changes the current user password after validating the old password.

Example body:

```json
{
  "current_password": "old-pass",
  "new_password": "new-pass-123",
  "confirm_password": "new-pass-123"
}
```

#### `GET /settings/actual`

Returns all configuration values exposed by the config manager.

#### `GET /settings/actual/<key>`

Returns a single config value.

#### `PUT /settings/actual/<key>`

Updates a config value.

### Developer note

This blueprint spans two layers:

- user profile data stored in the database
- application configuration stored in the config manager

Do not treat them as the same thing.

## 5.9 Users Blueprint

File: `api/users_api.py`

This is the most security-sensitive blueprint in the project. It handles user lifecycle, authentication, registration, and password recovery.

### Main routes

- `GET /users`: list users with pagination
- `GET /users/<user_id>`: fetch one user
- `POST /users`: create a user
- `PUT /users/<target_user_id>`: update a user
- `DELETE /users/<target_user_id>`: disable a user
- `POST /users/reset-password`: request a reset code
- `POST /users/validate-code`: verify reset code
- `POST /users/reset-password/change-password`: set a new password after verification
- `POST /login`: API login
- `POST /register`: API registration
- `GET /suggest/vendors`: vendor suggestions

### Password recovery flow

1. The user submits an email to `/users/reset-password`
2. The backend generates a 6-digit code and stores it in `password_resets`
3. The code is emailed to the user
4. The user submits the code to `/users/validate-code`
5. If valid, the user can call `/users/reset-password/change-password`

### Example reset request

```json
{
  "email": "usuario@ejemplo.com"
}
```

### Example login request

```json
{
  "username": "usuario",
  "password": "secret123"
}
```

### Security note

Any user-related route should be treated as sensitive because it touches credentials, roles, or account state.

## 5.10 Metrics Blueprint

File: `api/metrics_api.py`

This blueprint exposes analytics and dashboard KPIs.

### Core endpoints

- `GET /stats`: dashboard counters
- `GET /metrics`: detailed analytics for a date range or period
- `GET /never-sold`: products with no sale history

### What it returns

Typical metrics include:

- revenue
- sales count
- units sold
- average ticket
- top products
- sales over time
- sales by weekday and hour
- inventory risk indicators

### Example request

```bash
GET /metrics?period=30
```

### Example use case

This is the endpoint family you use when building charts, trend cards, or operational alerts in the dashboard.

## 6. Best Practices for Extending the API

When adding a new route:

- protect it with `require_auth` or a role decorator if the action is sensitive
- use `handle_db_error()` for persistence failures
- keep business logic atomic when it mutates sales or inventory
- return normalized JSON objects instead of raw tuples
- add `audit_action()` for any operation that should be traceable

### Example pattern

```python
@blueprint.route("/thing", methods=["POST"])
@require_role(ROLES.ADMIN, ROLES.ROOT)
@audit_action("product", "create")
def create_thing():
    data = request.get_json() or {}
    try:
        db.execute_query("INSERT INTO ...", (...,))
        return jsonify({"message": "Created"}), 201
    except Exception as e:
        return handle_db_error(e, "create_thing")
```

## 7. What To Read Next

If you want a full picture of the data flow, read this document together with:

- `docs/database.md` for the schema and connector layer
- `tools/audit_decorator.py` for audit generation rules
- `api/error_handlers.py` for response normalization
- `api/auth_utils.py` for auth and role gating

## 8. Summary

The API layer is designed as a thin but opinionated boundary. It does three things well:

- protects state-changing operations
- translates domain failures into consistent HTTP responses
- keeps business actions traceable through audit logging

That is the right shape for a Flask codebase that is expected to grow: the routes remain readable, the database stays centralized, and the caller receives predictable behavior.
