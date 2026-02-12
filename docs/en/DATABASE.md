# Database - SQLite

## Overview

StockManager uses SQLite as its local database engine, providing:
- Zero-configuration: No separate server required
- Portability: Single `.db` file contains everything
- Performance: Optimized for local operations
- Reliability: ACID compliant with transactions

## File Location

### Development

```bash
# Default
./bd/database.db

# Or configured via .env
DB_PATH=/custom/path/database.db
```

### Production (Packaged)

| Operating System | Location |
|------------------|----------|
| **Windows** | `%APPDATA%\StockManager\data\database.db` |
| **Linux** | `~/.stock_manager/data/database.db` |
| **macOS** | `~/.stock_manager/data/database.db` |

**Reason**: Avoid permission issues in read-only installation directories.

**Implementation**: See `bd/bdInstance.py` function `get_db_path()`

## Database Schema

### ER (Entity-Relationship) Diagram

```
┌─────────────────┐
│     users       │
│─────────────────│
│ id (PK)         │◄─┐
│ username (UQ)   │  │
│ password        │  │ Created by
│ email           │  │
│ role            │  │
└─────────────────┘  │
                     │
┌─────────────────┐  │
│     items       │  │
│─────────────────│  │
│ id (PK)         │◄─┼──┐
│ barrs_code (UQ) │  │  │
│ name            │  │  │
│ description     │  │  │ Sold
│ quantity        │  │  │
│ min_quantity    │  │  │
│ price           │  │  │
│ status          │  │  │
└─────────────────┘  │  │
         ▲           │  │
         │           │  │
         │ Item      │  │
         │           │  │
         │      ┌────┴──▼───────┐
         │      │    sells      │
         │      │───────────────│
         │      │ id (PK)       │
         └──────┤ item_id (FK)  │
                │ date          │
                └───────┬───────┘
                        │
                        │ Details
                        │
                ┌───────▼───────┐
                │    details    │
                │───────────────│
                │ id (PK)       │
                │ sell_id (FK)  │
                │ item_id (FK)  │
                │ quantity      │
                │ price         │
                └───────────────┘
```

### Table: `users`

Stores system user information.

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,  -- PBKDF2:SHA256 hash
    email TEXT NOT NULL,
    role TEXT NOT NULL       -- 'admin' or 'user'
);
```

**Automatic indexes:**
- `UNIQUE INDEX` on `username`

**Example data:**
```sql
INSERT INTO users (username, password, email, role) 
VALUES ('admin', 'pbkdf2:sha256:...',  'admin@company.com', 'admin');
```

**Common queries:**
```sql
-- Login
SELECT id, password, role 
FROM users 
WHERE username = ?;

-- Check if user exists
SELECT id FROM users 
WHERE username = ? OR email = ?;

-- Update email
UPDATE users 
SET email = ? 
WHERE id = ?;
```

### Table: `items`

Product inventory.

```sql
CREATE TABLE items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    barrs_code TEXT UNIQUE,       -- Can be NULL
    description TEXT,
    name TEXT NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 0,
    min_quantity INTEGER NOT NULL DEFAULT 5,
    price REAL NOT NULL,
    status INTEGER NOT NULL DEFAULT 1  -- 1=active, 0=disabled
);
```

**Constraints:**
- `name` is mandatory
- `barrs_code` is unique (but can be NULL for multiple products without code)
- `status` controls if product is active

**Example data:**
```sql
INSERT INTO items (barrs_code, name, description, quantity, min_quantity, price, status)
VALUES 
    ('7501234567890', 'HP Laptop 15', 'HP 15-inch laptop, 8GB RAM', 10, 3, 599.99, 1),
    ('7501234567891', 'Logitech Mouse', 'Wireless mouse', 50, 10, 25.50, 1),
    (NULL, 'Technical Service', 'Repair service per hour', 999, 0, 45.00, 1);
```

**Common queries:**
```sql
-- Search by barcode
SELECT id, barrs_code, name, description, quantity, price 
FROM items 
WHERE barrs_code = ?;

-- Products with low stock
SELECT id, name, quantity, min_quantity
FROM items 
WHERE quantity <= min_quantity 
  AND status = 1
ORDER BY quantity ASC;

-- Products out of stock
SELECT id, name
FROM items 
WHERE quantity = 0 
  AND status = 1;

-- Search products (autocomplete)
SELECT id, name, barrs_code, price, quantity
FROM items
WHERE status = 1 
  AND (name LIKE ? OR barrs_code LIKE ?)
LIMIT 10;
```

### Table: `sells`

Sales transaction registry.

```sql
CREATE TABLE sells (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (item_id) REFERENCES items(id)
);
```

**Note**: In bulk sales, `item_id` is used for the first product, but complete details are in `details`.

**Example data:**
```sql
INSERT INTO sells (item_id, date) 
VALUES (1, CURRENT_TIMESTAMP);
```

**Common queries:**
```sql
-- Sales today
SELECT COUNT(*) 
FROM sells 
WHERE DATE(date) = DATE('now');

-- Sales between dates
SELECT s.id, s.date, i.name
FROM sells s
JOIN details d ON s.id = d.sell_id
JOIN items i ON d.item_id = i.id
WHERE DATE(s.date) BETWEEN ? AND ?
ORDER BY s.date DESC;

-- Total monthly sales
SELECT 
    DATE(s.date) as date,
    COUNT(DISTINCT s.id) as num_sales,
    SUM(d.quantity * d.price) as total_sales
FROM sells s
JOIN details d ON s.id = d.sell_id
WHERE strftime('%Y-%m', s.date) = strftime('%Y-%m', 'now')
GROUP BY DATE(s.date)
ORDER BY date DESC;
```

### Table: `details`

Product details per sale.

```sql
CREATE TABLE details (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sell_id INTEGER NOT NULL,
    item_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    price REAL NOT NULL,  -- Price at sale time
    FOREIGN KEY (sell_id) REFERENCES sells(id),
    FOREIGN KEY (item_id) REFERENCES items(id)
);
```

**Why duplicate the price?**  
Price is captured at sale time to maintain correct history, even if product price changes later.

**Example data:**
```sql
-- Sale of 2 different products
INSERT INTO details (sell_id, item_id, quantity, price) VALUES
    (1, 1, 2, 599.99),  -- 2 laptops
    (1, 2, 1, 25.50);   -- 1 mouse
```

**Common queries:**
```sql
-- Details of a specific sale
SELECT 
    i.name,
    d.quantity,
    d.price,
    (d.quantity * d.price) as subtotal
FROM details d
JOIN items i ON d.item_id = i.id
WHERE d.sell_id = ?;

-- Top selling products
SELECT 
    i.id,
    i.name,
    SUM(d.quantity) as total_sold,
    SUM(d.quantity * d.price) as revenue
FROM details d
JOIN items i ON d.item_id = i.id
JOIN sells s ON d.sell_id = s.id
WHERE DATE(s.date) >= DATE('now', '-30 days')
GROUP BY i.id, i.name
ORDER BY total_sold DESC
LIMIT 10;
```

## SQLite Configuration

### Used Pragmas

```sql
PRAGMA foreign_keys = ON;           -- Referential integrity
PRAGMA journal_mode = WAL;          -- Write-Ahead Logging
PRAGMA synchronous = NORMAL;        -- Security/speed balance
PRAGMA cache_size = -8000;          -- 8MB cache
```

**Why WAL (Write-Ahead Logging)?**

```
Default Mode (DELETE):
┌─────────┐
│ Reads   │ → BLOCKED during writes
└─────────┘

WAL Mode:
┌─────────┐     ┌──────────┐
│ Reads   │ ←→  │ Writes   │ → Concurrent!
└─────────┘     └──────────┘
```

**Benefits:**
- Reads don't block writes
- Writes don't block reads
- Better overall performance
- More robust to crashes

**Trade-off:**
- Generates additional `-wal` file (temporary)

### Context Managers

All operations use context managers to guarantee correct transactions:

```python
# Implementation in bd/bdConector.py
@contextlib.contextmanager
def _cursor(self):
    conn = self._connect()
    try:
        cur = conn.cursor()
        yield cur
        conn.commit()  # Auto-commit if OK
    except sqlite3.Error as e:
        conn.rollback()  # Auto-rollback on error
        raise DatabaseError(f"Database error: {e}")
    finally:
        conn.close()  # Always close connection
```

**Usage example:**
```python
with self._cursor() as cur:
    cur.execute("INSERT INTO items (...) VALUES (?)", (data,))
    # If reaches here: automatic commit
    # If exception: automatic rollback
```

## Common Operations

### Register a Simple Sale

```python
def record_sale(self, item_id, quantity):
    with self._cursor() as cur:
        # 1. Insert sale
        cur.execute("INSERT INTO sells (item_id) VALUES (?)", (item_id,))
        sell_id = cur.lastrowid
        
        # 2. Get current price
        cur.execute("SELECT price, quantity FROM items WHERE id = ?", (item_id,))
        price, current_qty = cur.fetchone()
        
        # 3. Validate stock
        if current_qty < quantity:
            raise ValueError("Insufficient stock")
        
        # 4. Insert detail
        cur.execute(
            "INSERT INTO details (sell_id, item_id, quantity, price) VALUES (?, ?, ?, ?)",
            (sell_id, item_id, quantity, price)
        )
        
        # 5. Update stock
        cur.execute(
            "UPDATE items SET quantity = ? WHERE id = ?",
            (current_qty - quantity, item_id)
        )
    # Automatic commit on context manager exit
```

### Bulk Sale

```python
def record_bulk_sale(self, items):
    # items = [{"item_id": 1, "quantity": 2}, {"item_id": 3, "quantity": 1}]
    with self._cursor() as cur:
        # 1. Create sale
        cur.execute("INSERT INTO sells (item_id) VALUES (?)", (items[0]["item_id"],))
        sell_id = cur.lastrowid
        
        # 2. For each product
        for item in items:
            item_id = item["item_id"]
            quantity = item["quantity"]
            
            # Get data
            cur.execute("SELECT price, quantity FROM items WHERE id = ?", (item_id,))
            price, current_qty = cur.fetchone()
            
            # Validate stock
            if current_qty < quantity:
                raise ValueError(f"Insufficient stock for item {item_id}")
            
            # Insert detail
            cur.execute(
                "INSERT INTO details (sell_id, item_id, quantity, price) VALUES (?, ?, ?, ?)",
                (sell_id, item_id, quantity, price)
            )
            
            # Update stock
            cur.execute(
                "UPDATE items SET quantity = ? WHERE id = ?",
                (current_qty - quantity, item_id)
            )
    return sell_id
```

## Analysis Queries

### Dashboard Stats

```sql
-- Main KPIs
SELECT
    (SELECT COUNT(*) FROM items WHERE status = 1) as total_products,
    (SELECT COUNT(*) FROM items WHERE quantity <= min_quantity AND status = 1) as low_stock,
    (SELECT COUNT(*) FROM sells WHERE DATE(date) = DATE('now')) as sales_today;
```

### Top 10 Products

```sql
SELECT 
    i.id,
    i.name,
    i.barrs_code,
    SUM(d.quantity) as quantity_sold,
    SUM(d.quantity * d.price) as revenue_generated
FROM details d
JOIN items i ON d.item_id = i.id
JOIN sells s ON d.sell_id = s.id
WHERE DATE(s.date) >= DATE('now', '-30 days')
GROUP BY i.id, i.name, i.barrs_code
ORDER BY quantity_sold DESC
LIMIT 10;
```

### Sales by Day of Week

```sql
SELECT 
    CASE CAST(strftime('%w', date) AS INTEGER)
        WHEN 0 THEN 'Sunday'
        WHEN 1 THEN 'Monday'
        WHEN 2 THEN 'Tuesday'
        WHEN 3 THEN 'Wednesday'
        WHEN 4 THEN 'Thursday'
        WHEN 5 THEN 'Friday'
        WHEN 6 THEN 'Saturday'
    END as weekday,
    COUNT(*) as num_sales
FROM sells
WHERE DATE(date) >= DATE('now', '-30 days')
GROUP BY strftime('%w', date)
ORDER BY num_sales DESC;
```

## Maintenance

### Database Backup

```bash
# Simple backup (copy file)
cp database.db database_backup_$(date +%Y%m%d).db

# Backup with SQLite (safer)
sqlite3 database.db ".backup database_backup_$(date +%Y%m%d).db"

# Programmatic backup from Python
import sqlite3
import shutil

source = "database.db"
backup = f"database_backup_{datetime.now().strftime('%Y%m%d')}.db"
shutil.copy2(source, backup)
```

### Vacuum (Optimization)

```sql
-- Recover space after many DELETEs
VACUUM;

-- Or configure auto-vacuum
PRAGMA auto_vacuum = INCREMENTAL;
PRAGMA incremental_vacuum(100);
```

### Check Integrity

```sql
PRAGMA integrity_check;
-- Expected result: ok
```

### Analyze Performance

```sql
EXPLAIN QUERY PLAN
SELECT * FROM items WHERE name LIKE '%laptop%';

-- If you see SCAN TABLE: consider adding index
CREATE INDEX idx_items_name ON items(name);
```

## Troubleshooting

### "database is locked"

**Cause**: Another connection has exclusive lock

**Solutions:**
1. Ensure all connections are closed
2. Use WAL mode (already configured)
3. Increase timeout: `connection.execute("PRAGMA busy_timeout = 5000")`

### "unable to open database file"

**Cause**: Permission issues or incorrect path

**Solutions:**
1. Verify directory exists and is writable
2. In production, use user paths (see `bd/bdInstance.py`)
3. Check permissions: `ls -l database.db`

### Database Corruption

**Prevention:**
- Use WAL mode
- `PRAGMA synchronous = NORMAL` or higher
- No forced kills during writes

**Recovery:**
```sql
-- Verify
PRAGMA integrity_check;

-- If corrupted, try dump/restore
sqlite3 database.db .dump > backup.sql
rm database.db
sqlite3 database.db < backup.sql
```

## References

- [Official SQLite](https://www.sqlite.org/docs.html)
- [WAL Mode](https://www.sqlite.org/wal.html)
- [Local Implementation](../../bd/bdConector.py)

## See Also

- [Architecture](ARCHITECTURE.md) - How DB integrates
- [API](API.md) - Endpoints using the DB
- [Development](DEVELOPMENT.md) - Local setup
