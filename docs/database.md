# Database Documentation

This document explains the database layer of StockManager from the perspective of a senior Python developer. It focuses on schema design, relationships, transactional behavior, public access methods, and practical usage examples.

## 1. Overview

StockManager uses SQLite as its persistence layer and wraps all database access behind the `BDConector` class. The class is organized with mixins so each domain area remains isolated and easier to maintain:

- `UsersMixin`: user management
- `ItemsMixin`: inventory and product operations
- `SalesMixin`: sales registration and sale queries
- `MetricsMixin`: KPIs and reporting
- `PasswordResetMixin`: password recovery codes
- `NotificationsMixin`: in-app notifications
- `ApplicationsMixin`: user application workflow
- `AuditMixin`: audit trail logging

The central design goal is to keep the SQL surface area small and predictable. Most application code should not talk to SQLite directly. It should go through `BDConector` so that transactions, logging, error translation, and connection reuse stay consistent.

## 2. Connection Model

`BDConector` uses a thread-local connection pool pattern. Each request thread gets its own SQLite connection, which is reused for the lifetime of that thread.

### Why this matters

- Avoids opening and closing a connection on every query
- Keeps request-level access efficient
- Reduces boilerplate in routes and services
- Makes transaction boundaries explicit

### Connection lifecycle

- `BDConector.__init__(db_path)` stores the database file path
- `_get_conn()` returns the current thread connection or creates one if needed
- `close_conn()` closes the current thread connection and resets the thread-local handle
- `_cursor()` is the main transactional context manager used by query methods

### Operational note

SQLite is safe and effective for small to medium workloads, but it is still a file-based database. Writes are serialized at the database level, so the application should keep transactions short and focused.

## 3. Core Tables

The schema is initialized in `init_db()`. The method creates tables if they do not exist and then applies incremental migrations.

### 3.1 `users`

Stores application users and their security state.

| Column | Type | Constraints | Purpose |
| --- | --- | --- | --- |
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT UNIQUE | Internal user identifier |
| `username` | TEXT | NOT NULL | Login/display name |
| `password` | TEXT | NOT NULL | Password hash |
| `email` | TEXT | NOT NULL UNIQUE | Unique email address |
| `role` | TEXT | NOT NULL | Role such as root/admin/vendor |
| `status` | INTEGER | NOT NULL DEFAULT 1 | Active/inactive flag |
| `application` | TEXT | NOT NULL DEFAULT 'pending' | Registration workflow state |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Creation timestamp |
| `history` | TEXT | nullable | Free-form history or audit payload |

#### Notes

- Passwords are expected to be stored as hashes, not plaintext.
- `application` is used by the approval flow.
- `status` controls whether the account can operate in the system.

### 3.2 `items`

Stores inventory products.

| Column | Type | Constraints | Purpose |
| --- | --- | --- | --- |
| `id` | INTEGER | PRIMARY KEY NOT NULL | Product identifier |
| `barrs_code` | TEXT | UNIQUE | Barcode or internal code |
| `description` | TEXT | nullable | Product description |
| `name` | TEXT | NOT NULL | Product name |
| `quantity` | INTEGER | NOT NULL DEFAULT 0 | Current stock |
| `min_quantity` | INTEGER | NOT NULL DEFAULT 5 | Minimum stock threshold |
| `price` | REAL | NOT NULL | Sale price |
| `expiration_date` | TEXT | nullable | Expiration date string |
| `status` | INTEGER | NOT NULL DEFAULT 1 | Active/inactive flag |
| `notified_low_stock` | INTEGER | NOT NULL DEFAULT 0 | Prevents repeated alerts |
| `created_at` | TEXT | nullable | Creation timestamp |
| `updated_at` | TEXT | nullable | Last update timestamp |

#### Notes

- `barrs_code` is optional in practice; methods normalize empty values to `None`.
- `notified_low_stock` is used to avoid duplicate stock alerts.
- `expiration_date` is stored as text, so date parsing is the responsibility of the application layer.

### 3.3 `sells`

Stores sale headers.

| Column | Type | Constraints | Purpose |
| --- | --- | --- | --- |
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Sale identifier |
| `item_id` | INTEGER | NOT NULL | Legacy or primary item reference |
| `date` | TEXT | NOT NULL | Sale date/time |
| `vendor_id` | INTEGER | NOT NULL REFERENCES users(id) | Seller user |
| `payment_method` | TEXT | NOT NULL DEFAULT 'Efectivo' | Payment method |

#### Notes

- The table currently keeps a single `item_id` field even though `details` supports multi-item sales.
- In practice, `details` is the authoritative sale-line table.

### 3.4 `details`

Stores sale lines.

| Column | Type | Constraints | Purpose |
| --- | --- | --- | --- |
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Line identifier |
| `sell_id` | INTEGER | NOT NULL | Parent sale |
| `item_id` | INTEGER | NOT NULL | Sold product |
| `quantity` | INTEGER | NOT NULL | Units sold |
| `price` | REAL | NOT NULL | Unit price at sale time |
| `vendor_id` | INTEGER | NOT NULL REFERENCES users(id) | Seller user |
| `payment_method` | TEXT | NOT NULL DEFAULT 'Efectivo' | Payment method |

#### Notes

- This table is the real source of truth for multi-item sales.
- Sale totals are not stored directly; they are computed from `quantity * price`.

### 3.5 `password_resets`

Stores recovery codes for password reset flows.

| Column | Type | Constraints | Purpose |
| --- | --- | --- | --- |
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Reset row identifier |
| `email` | TEXT | NOT NULL | Target email |
| `code` | TEXT | NOT NULL | Reset code |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Issue timestamp |

#### Notes

- Codes expire logically after 15 minutes according to the query logic.
- The table is append-only from the application perspective; old rows are deleted when needed.

### 3.6 `item_attributes`

Defines custom attribute metadata for products.

| Column | Type | Constraints | Purpose |
| --- | --- | --- | --- |
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Attribute identifier |
| `name` | TEXT | NOT NULL UNIQUE | Human-readable name |
| `code` | TEXT | NOT NULL UNIQUE | Stable machine code |
| `data_type` | TEXT | NOT NULL | Attribute type |
| `required` | INTEGER | NOT NULL DEFAULT 0 | Required flag |
| `status` | INTEGER | NOT NULL DEFAULT 1 | Active/inactive flag |

### 3.7 `item_attribute_values`

Stores values for product attributes.

| Column | Type | Constraints | Purpose |
| --- | --- | --- | --- |
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Value row identifier |
| `item_id` | INTEGER | NOT NULL | Target product |
| `attribute_id` | INTEGER | NOT NULL | Attribute definition |
| `value` | TEXT | nullable | Attribute value |
| `updated_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Last update |

#### Constraints

- `UNIQUE(item_id, attribute_id)` ensures one value per attribute per item.
- Foreign keys link the value to both the product and the attribute definition.

### 3.8 `notifications`

Stores in-app notifications.

| Column | Type | Constraints | Purpose |
| --- | --- | --- | --- |
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Notification identifier |
| `user_id` | INTEGER | NOT NULL | Recipient user |
| `title` | TEXT | NOT NULL | Short title |
| `message` | TEXT | nullable | Detailed message |
| `type` | TEXT | DEFAULT 'info' CHECK(...) | info/warning/success/error |
| `action_url` | TEXT | nullable | Optional navigation target |
| `is_read` | INTEGER | DEFAULT 0 | Read flag |
| `created_at` | TEXT | DEFAULT CURRENT_TIMESTAMP | Creation timestamp |

#### Notes

- The `type` column is constrained with a `CHECK` clause.
- `ON DELETE CASCADE` is defined for the foreign key on `user_id`.

### 3.9 `audit_log`

Stores audit events for security and operational traceability.

| Column | Type | Constraints | Purpose |
| --- | --- | --- | --- |
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Audit identifier |
| `user_id` | INTEGER | NOT NULL | Actor user |
| `action` | TEXT | NOT NULL | Action name |
| `entity_type` | TEXT | NOT NULL | Type of entity affected |
| `entity_id` | INTEGER | nullable | Specific entity identifier |
| `old_value` | TEXT | nullable | Previous state as JSON |
| `new_value` | TEXT | nullable | New state as JSON |
| `description` | TEXT | nullable | Human-readable explanation |
| `ip_address` | TEXT | nullable | Source IP address |
| `timestamp` | TEXT | DEFAULT CURRENT_TIMESTAMP | Event timestamp |
| `status` | TEXT | DEFAULT 'success' | Result of the action |

#### Notes

- `old_value` and `new_value` are serialized with `json.dumps()`.
- The table is designed for forensic analysis, not for application logic.

## 4. Relationships

The database uses a mix of explicit foreign keys and application-level references.

### Key relationships

- `sells.vendor_id` -> `users.id`
- `details.vendor_id` -> `users.id`
- `details.sell_id` -> `sells.id`
- `details.item_id` -> `items.id`
- `notifications.user_id` -> `users.id`
- `audit_log.user_id` -> `users.id`
- `item_attribute_values.item_id` -> `items.id`
- `item_attribute_values.attribute_id` -> `item_attributes.id`
- `password_resets.email` is not a foreign key, but it logically maps to `users.email`

### Practical interpretation

- `users` is the root identity table.
- `items` is the inventory master table.
- `sells` represents the sale header.
- `details` represents the sale lines and should be used for most reporting.
- `audit_log` and `notifications` are auxiliary but important operational tables.

## 5. Initialization and Migrations

`init_db()` performs two distinct phases:

1. Creates all core tables if they do not exist.
2. Runs incremental migrations to support schema evolution on existing databases.

### Migration style

The migration list is idempotent. It attempts to add missing columns or normalize older schemas without breaking fresh installs.

#### Example migration targets in the codebase

- `users.status`
- `users.created_at`
- `users.history`
- `users.application`
- `items.expiration_date`
- `items.notified_low_stock`
- `items.created_at`
- `items.updated_at`
- `sells.vendor_id`
- `sells.payment_method`
- `details.vendor_id`
- `details.payment_method`

### Root user bootstrap

After schema initialization, the connector runs logic to create a default root user if none exists, then validates that only one root user is present.

This matters because the system expects a privileged account to exist for administrative access.

## 6. Transaction Model

The connector exposes two important execution primitives:

- `_cursor()` for automatic commit/rollback around query work
- `transaction()` for multi-step operations that should remain atomic

### `_cursor()`

Use this for ordinary queries where the database method should manage commit and rollback automatically.

### `transaction()`

Use this when a higher-level operation needs multiple statements to succeed or fail together. This is the correct choice for sale registration and sale updates.

### Why atomicity matters

Examples that must be atomic:

- Creating a sale and its details
- Deducting stock after the sale row exists
- Restoring stock before replacing sale lines in an update

If one statement fails midway, the whole transaction should roll back so inventory does not drift.

## 7. Public Database API

The mixins expose the main operations used by the rest of the app.

### Users

- `user_exists(username, email)` checks duplicates
- `add_user(...)` inserts a new user
- `get_user_by_email(email)` fetches user identity and role data
- `get_username_by_id(user_id)` resolves a display name

### Applications

- `get_pending_applications(page, limit)` paginates pending users
- `approve_application(user_id)` sets `application='accepted'` and `status=1`
- `reject_application(user_id)` sets `application='rejected'`

### Items

- `add_item(...)` inserts a product
- `get_item_details(item_id)` returns the product detail payload
- `get_item_by_id(item_id)` returns a normalized product dict
- `get_all_items()` returns active items
- `disable_item(item_id)` and `enable_item(item_id)` toggle `status`
- `update_item_barcode(item_id, new_barrs_code)` updates the barcode field
- `check_and_notify_low_stock(user_id)` creates warning notifications
- `generate_barcode_image(barrs_code)` renders a barcode image

### Sales

- `get_dashboard_stats()` returns dashboard counters
- `record_product_sale(item_id, quantity, vendor_id, payment_method)` registers a single-item sale
- `record_bulk_sale(items, vendor_id, payment_method)` registers a multi-item sale
- `get_sale_by_id(sale_id)` returns sale header plus sale lines
- `update_sale(sale_id, items, vendor_id, payment_method)` replaces sale lines and recalculates stock

### Metrics

- `get_metrics_data(start_date, end_date, prev_start_date, prev_end_date)` returns global KPIs
- `get_vendors_metrics(start_date, end_date, prev_start_date, prev_end_date)` returns per-vendor performance

### Notifications

- `create_notification(...)`
- `get_unread_notifications(user_id, limit)`
- `get_all_notifications(user_id, limit, offset)`
- `mark_as_read(notification_id)`
- `mark_all_as_read(user_id)`
- `get_unread_count(user_id)`
- `delete_notification(notification_id)`

### Password reset

- `save_reset_code(email, code)`
- `get_reset_code(email)`
- `delete_reset_code(email)`
- `update_user_password(email, new_password)`
- `verify_code(email, code)`

### Audit

- `log_audit(...)`
- `get_audit_log(...)`
- `get_entity_audit_trail(entity_type, entity_id)`

## 8. Query Helper Behavior

The connector also exposes general-purpose helpers:

- `execute_query(query, params=(), fetch=True)`
- `execute_many(query, params_list)`
- `create_table(table_name, columns)`
- `get_count(query, params=())`
- `get_single_row(query, params=())`
- `get_all_rows(query, params=())`

### `execute_query()`

This is the main read/write helper. Its behavior depends on `fetch`:

- `fetch=True`: returns rows
- `fetch=False`: returns affected-row count or a write result

### `execute_many()`

Use this for batch inserts or batch updates where the same SQL statement runs against many parameter sets.

### `create_table()`

Useful for ad hoc tables, tests, or future module extensions, but core schema should remain centralized in `init_db()`.

## 9. Practical Examples

### 9.1 Create a new user

```python
from werkzeug.security import generate_password_hash
from bd.bdInstance import db

password_hash = generate_password_hash("SuperSecret123")
db.add_user(
    username="admin",
    password=password_hash,
    email="admin@example.com",
    role="root",
    status=1,
    application="accepted",
)
```

### 9.2 Insert a product

```python
from bd.bdInstance import db
from tools.local_time import localDate

db.add_item(
    barrs_code="PRD0001",
    description="Coffee beans 1kg",
    name="Premium Coffee",
    quantity=20,
    min_quantity=5,
    expiration_date="2026-12-31",
    price=12.5,
)
```

### 9.3 Register a sale

```python
from bd.bdInstance import db

db.record_product_sale(
    item_id=1,
    quantity=2,
    vendor_id=3,
    payment_method="Efectivo",
)
```

### 9.4 Register a multi-item sale

```python
items = [
    {"item_id": 1, "quantity": 2},
    {"item_id": 4, "quantity": 1},
]

sale_id = db.record_bulk_sale(items, vendor_id=3, payment_method="Tarjeta")
```

### 9.5 Read unread notifications

```python
notifications = db.get_unread_notifications(user_id=3, limit=10)
```

### 9.6 Write an audit record

```python
db.log_audit(
    actor_id=1,
    action="UPDATE",
    entity_type="item",
    entity_id=10,
    old_value={"quantity": 5},
    new_value={"quantity": 8},
    description="Stock adjusted after inventory count",
    ip_address="127.0.0.1",
)
```

## 10. Usage Patterns and Best Practices

### Recommended

- Always go through `BDConector` instead of raw `sqlite3` in application code.
- Keep transactions short.
- Store passwords only as hashes.
- Prefer `details` for reporting sales totals.
- Normalize dates at the application layer before writing them.
- Use `log_audit()` from routes or service boundaries when a user action should be traceable.

### Avoid

- Long-running transactions
- Directly mutating tables outside the connector
- Relying on implicit type conversion for dates or money
- Building reports from `sells` alone when the line-level data lives in `details`

## 11. Error Handling Model

The database layer uses custom exceptions from `bd/bdErrors.py`.

- `DatabaseError`: generic persistence-layer failure
- `StockError`: domain-level stock exception

Most mixins catch low-level exceptions and rethrow them as `DatabaseError` so the rest of the app can handle failures consistently.

### Why wrap errors

- Keeps SQLite details out of route handlers
- Allows the UI to display domain-friendly messages
- Makes the code easier to test

## 12. Operational Checklist

Before shipping a change to the database layer, verify:

- The schema still matches the expectations of the mixins
- New columns are covered by initialization or migration logic
- Transactional operations remain atomic
- Read queries return stable shapes for the UI
- New writes are either validated or wrapped in a domain exception

## 13. Summary

The database layer in StockManager is intentionally centralized. `BDConector` is the contract between the application and SQLite, while mixins separate business domains without fragmenting the persistence rules. If you extend the system, keep schema changes in one place, preserve atomicity for stock and sales operations, and document every new table or column with the same level of rigor.
