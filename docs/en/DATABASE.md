# Database (SQLite)

This project uses SQLite for local storage. The data-access layer lives under `bd/` (mainly `bd/bdConector.py`) and the database file path is chosen in `bd/bdInstance.py`.

## `.db` file location

The path depends on whether you are in development or running a “frozen” PyInstaller binary.

- **Development (not frozen)**: uses `DB_PATH` (if set) or `./bd/database.db`.
- **Production / Packaged (PyInstaller, frozen)**: creates/uses `data/database.db` next to the executable (in a writable directory).

Notes:
- In frozen mode, `bd/bdInstance.py` ensures the `data/` directory exists.
- If you hit permission issues writing the DB (common in packaged apps), check the troubleshooting guide.

## Initialization and schema

Initialization happens automatically when importing `bd/bdInstance.py`:

- It instantiates `BDConector(db_path=...)`.
- It runs `db.init_db()`.

`init_db()` uses `CREATE TABLE IF NOT EXISTS`, so it is **idempotent**.

### Tables

#### `users`
System users.

Columns:
- `id` (INTEGER, PK, autoincrement)
- `username` (TEXT, unique, required)
- `password` (TEXT, required)
- `email` (TEXT, required)
- `role` (TEXT, required)

#### `items`
Inventory products.

Columns:
- `id` (INTEGER, PK, autoincrement)
- `barrs_code` (TEXT, unique, may be NULL)
- `description` (TEXT)
- `name` (TEXT, required)
- `quantity` (INTEGER, required, default 0)
- `min_quantity` (INTEGER, required, default 5)
- `price` (REAL, required)
- `status` (INTEGER, required, default 1)

Conventions:
- `status = 1` → active
- `status = 0` → disabled (soft delete)

#### `sells`
Sales “header” table. In the current design it includes `item_id` and `date`. For multi-item sales, rows are detailed in `details`.

Columns:
- `id` (INTEGER, PK, autoincrement)
- `item_id` (INTEGER, FK to `items.id`)
- `date` (TIMESTAMP, default `CURRENT_TIMESTAMP`)

Note: for bulk sales, `item_id` is inserted using the first item, while the real per-item data is stored in `details`.

#### `details`
Per-item rows for each sale.

Columns:
- `id` (INTEGER, PK, autoincrement)
- `sell_id` (INTEGER, FK to `sells.id`, required)
- `item_id` (INTEGER, FK to `items.id`, required)
- `quantity` (INTEGER, required)
- `price` (REAL, required)

## Key operations

### Record multi-item sale (bulk)
`BDConector.record_bulk_sale(items)`:
- Validates the list is not empty.
- Inserts one row into `sells`.
- For each item:
  - Reads current `price` and `quantity` from `items`.
  - Validates there is enough stock.
  - Inserts into `details` with `quantity` and `price` (captures price at the time of sale).
  - Updates stock in `items`.

Everything runs inside the connector transaction context (commit/rollback based on success).

### Disable/enable item (soft delete)
- `disable_item(item_id)` → `UPDATE items SET status = 0 ...`
- `enable_item(item_id)` → `UPDATE items SET status = 1 ...`

## Backups and migrations

There is no migrations framework (e.g., Alembic) built in.

Practical recommendation for schema changes:
- Version SQL changes manually and document them.
- Provide a migration script if the schema evolves (or recreate the DB in non-production environments).

## Related environment variables

- `DB_PATH`: database path in development.

