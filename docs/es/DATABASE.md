# Base de datos (SQLite)

Este proyecto usa SQLite como almacenamiento local. La capa de acceso está en `bd/` (principalmente `bd/bdConector.py`) y la ruta del archivo de base de datos se decide en `bd/bdInstance.py`.

## Ubicación del archivo `.db`

La ruta depende de si estás en desarrollo o ejecutando el binario “frozen” (PyInstaller).

- **Desarrollo (no frozen)**: usa `DB_PATH` (si existe) o `./bd/database.db`.
- **Producción / Empaquetado (PyInstaller, frozen)**: crea/usa `data/database.db` junto al ejecutable (en un directorio escribible).

Notas:
- En modo frozen, `bd/bdInstance.py` asegura que exista el directorio `data/`.
- Si hay problemas de permisos al escribir la BD (típico en empaquetados), revisa la sección de troubleshooting.

## Inicialización y esquema

La inicialización se hace automáticamente al importar `bd/bdInstance.py`:

- Se instancia `BDConector(db_path=...)`.
- Se ejecuta `db.init_db()`.

`init_db()` crea las tablas con `CREATE TABLE IF NOT EXISTS`, por lo que es **idempotente**.

### Tablas

#### `users`
Usuarios del sistema.

Campos:
- `id` (INTEGER, PK, autoincrement)
- `username` (TEXT, unique, requerido)
- `password` (TEXT, requerido)
- `email` (TEXT, requerido)
- `role` (TEXT, requerido)

#### `items`
Inventario de productos.

Campos:
- `id` (INTEGER, PK, autoincrement)
- `barrs_code` (TEXT, unique, puede ser NULL)
- `description` (TEXT)
- `name` (TEXT, requerido)
- `quantity` (INTEGER, requerido, default 0)
- `min_quantity` (INTEGER, requerido, default 5)
- `price` (REAL, requerido)
- `status` (INTEGER, requerido, default 1)

Convenciones:
- `status = 1` → activo
- `status = 0` → deshabilitado (baja lógica)

#### `sells`
Registro de ventas (transacciones). En el diseño actual, la tabla incluye `item_id` y un `date`. Para ventas con múltiples productos, se usa además la tabla `details`.

Campos:
- `id` (INTEGER, PK, autoincrement)
- `item_id` (INTEGER, FK a `items.id`)
- `date` (TIMESTAMP, default `CURRENT_TIMESTAMP`)

Nota: para ventas “bulk”, `item_id` se inserta con el primer item, y el detalle real de productos vendidos se guarda en `details`.

#### `details`
Detalle de productos vendidos por venta.

Campos:
- `id` (INTEGER, PK, autoincrement)
- `sell_id` (INTEGER, FK a `sells.id`, requerido)
- `item_id` (INTEGER, FK a `items.id`, requerido)
- `quantity` (INTEGER, requerido)
- `price` (REAL, requerido)

## Operaciones clave

### Registrar venta múltiple (bulk)
`BDConector.record_bulk_sale(items)`:
- Valida que la lista no esté vacía.
- Inserta un registro en `sells`.
- Para cada item:
  - Lee `price` y `quantity` actuales desde `items`.
  - Valida stock suficiente.
  - Inserta una fila en `details` con `quantity` y `price` (captura el precio del momento).
  - Actualiza el stock en `items`.

Todo ocurre dentro del contexto de cursor/transaction del conector (commit/rollback según éxito).

### Baja lógica / alta de producto
- `disable_item(item_id)` → `UPDATE items SET status = 0 ...`
- `enable_item(item_id)` → `UPDATE items SET status = 1 ...`

## Backups y migraciones

No hay un sistema de migraciones (tipo Alembic) integrado.

Recomendación práctica para cambios de esquema:
- Versionar cambios de SQL manualmente y documentarlos.
- Proveer un script de migración si el esquema evoluciona (o recrear BD en entornos no productivos).

## Variables de entorno relacionadas

- `DB_PATH`: ruta a la base de datos en desarrollo.

