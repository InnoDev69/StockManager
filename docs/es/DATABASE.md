# 💾 Base de Datos - SQLite

## 📋 Resumen

StockManager utiliza SQLite como motor de base de datos local, proporcionando:
- ✅ **Zero-configuration**: No requiere servidor separado
- ✅ **Portabilidad**: Un solo archivo `.db` contiene todo
- ✅ **Rendimiento**: Optimizado para operaciones locales
- ✅ **Confiabilidad**: ACID compliant con transacciones

## 📍 Ubicación del Archivo

### Desarrollo

```bash
# Por defecto
./bd/database.db

# O configurado via .env
DB_PATH=/ruta/personalizada/database.db
```

### Producción (Empaquetado)

| Sistema Operativo | Ubicación |
|-------------------|-----------|
| **Windows** | `%APPDATA%\StockManager\data\database.db` |
| **Linux** | `~/.stock_manager/data/database.db` |
| **macOS** | `~/.stock_manager/data/database.db` |

**Razón**: Evitar problemas de permisos en directorios de instalación de solo lectura.

**Implementación**: Ver `bd/bdInstance.py` función `get_db_path()`

## 🗂️ Esquema de Base de Datos

### Diagrama ER (Entity-Relationship)

```
┌─────────────────┐
│     users       │
│─────────────────│
│ id (PK)         │◄─┐
│ username (UQ)   │  │
│ password        │  │ Creó
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
│ description     │  │  │ Vendió
│ quantity        │  │  │
│ min_quantity    │  │  │
│ price           │  │  │
│ status          │  │  │
└─────────────────┘  │  │
         ▲           │  │
         │           │  │
         │ Item de   │  │
         │           │  │
         │      ┌────┴──▼───────┐
         │      │    sells      │
         │      │───────────────│
         │      │ id (PK)       │
         └──────┤ item_id (FK)  │
                │ date          │
                └───────┬───────┘
                        │
                        │ Detalles
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

### Tabla: `users`

Almacena información de usuarios del sistema.

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,  -- Hash PBKDF2:SHA256
    email TEXT NOT NULL,
    role TEXT NOT NULL       -- 'admin' o 'user'
);
```

**Índices automáticos:**
- `UNIQUE INDEX` en `username`

**Ejemplo de datos:**
```sql
INSERT INTO users (username, password, email, role) 
VALUES ('admin', 'pbkdf2:sha256:...',  'admin@empresa.com', 'admin');
```

**Consultas comunes:**
```sql
-- Login
SELECT id, password, role 
FROM users 
WHERE username = ?;

-- Verificar si usuario existe
SELECT id FROM users 
WHERE username = ? OR email = ?;

-- Actualizar email
UPDATE users 
SET email = ? 
WHERE id = ?;
```

### Tabla: `items`

Inventario de productos.

```sql
CREATE TABLE items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    barrs_code TEXT UNIQUE,       -- Puede ser NULL
    description TEXT,
    name TEXT NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 0,
    min_quantity INTEGER NOT NULL DEFAULT 5,
    price REAL NOT NULL,
    status INTEGER NOT NULL DEFAULT 1  -- 1=activo, 0=deshabilitado
);
```

**Restricciones:**
- `name` es obligatorio
- `barrs_code` es único (pero puede ser NULL para múltiples productos sin código)
- `status` controla si el producto está activo

**Ejemplo de datos:**
```sql
INSERT INTO items (barrs_code, name, description, quantity, min_quantity, price, status)
VALUES 
    ('7501234567890', 'Laptop HP 15', 'Laptop HP 15 pulgadas, 8GB RAM', 10, 3, 599.99, 1),
    ('7501234567891', 'Mouse Logitech', 'Mouse inalámbrico', 50, 10, 25.50, 1),
    (NULL, 'Servicio Técnico', 'Servicio de reparación por hora', 999, 0, 45.00, 1);
```

**Consultas comunes:**
```sql
-- Buscar por código de barras
SELECT id, barrs_code, name, description, quantity, price 
FROM items 
WHERE barrs_code = ?;

-- Productos con stock bajo
SELECT id, name, quantity, min_quantity
FROM items 
WHERE quantity <= min_quantity 
  AND status = 1
ORDER BY quantity ASC;

-- Productos sin stock
SELECT id, name
FROM items 
WHERE quantity = 0 
  AND status = 1;

-- Buscar productos (autocomplete)
SELECT id, name, barrs_code, price, quantity
FROM items
WHERE status = 1 
  AND (name LIKE ? OR barrs_code LIKE ?)
LIMIT 10;
```

### Tabla: `sells`

Registro de transacciones de venta.

```sql
CREATE TABLE sells (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (item_id) REFERENCES items(id)
);
```

**Nota**: En ventas múltiples (bulk), `item_id` se usa para el primer producto, pero los detalles completos están en `details`.

**Ejemplo de datos:**
```sql
INSERT INTO sells (item_id, date) 
VALUES (1, CURRENT_TIMESTAMP);
```

**Consultas comunes:**
```sql
-- Ventas del día
SELECT COUNT(*) 
FROM sells 
WHERE DATE(date) = DATE('now');

-- Ventas entre fechas
SELECT s.id, s.date, i.name
FROM sells s
JOIN details d ON s.id = d.sell_id
JOIN items i ON d.item_id = i.id
WHERE DATE(s.date) BETWEEN ? AND ?
ORDER BY s.date DESC;

-- Total de ventas del mes
SELECT 
    DATE(s.date) as fecha,
    COUNT(DISTINCT s.id) as num_ventas,
    SUM(d.quantity * d.price) as total_ventas
FROM sells s
JOIN details d ON s.id = d.sell_id
WHERE strftime('%Y-%m', s.date) = strftime('%Y-%m', 'now')
GROUP BY DATE(s.date)
ORDER BY fecha DESC;
```

### Tabla: `details`

Detalles de productos por cada venta.

```sql
CREATE TABLE details (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sell_id INTEGER NOT NULL,
    item_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    price REAL NOT NULL,  -- Precio al momento de la venta
    FOREIGN KEY (sell_id) REFERENCES sells(id),
    FOREIGN KEY (item_id) REFERENCES items(id)
);
```

**¿Por qué duplicar el precio?**  
El precio se captura al momento de la venta para mantener histórico correcto, incluso si el precio del producto cambia después.

**Ejemplo de datos:**
```sql
-- Venta de 2 productos diferentes
INSERT INTO details (sell_id, item_id, quantity, price) VALUES
    (1, 1, 2, 599.99),  -- 2 laptops
    (1, 2, 1, 25.50);   -- 1 mouse
```

**Consultas comunes:**
```sql
-- Detalle de una venta específica
SELECT 
    i.name,
    d.quantity,
    d.price,
    (d.quantity * d.price) as subtotal
FROM details d
JOIN items i ON d.item_id = i.id
WHERE d.sell_id = ?;

-- Productos más vendidos
SELECT 
    i.id,
    i.name,
    SUM(d.quantity) as total_vendido,
    SUM(d.quantity * d.price) as ingresos
FROM details d
JOIN items i ON d.item_id = i.id
JOIN sells s ON d.sell_id = s.id
WHERE DATE(s.date) >= DATE('now', '-30 days')
GROUP BY i.id, i.name
ORDER BY total_vendido DESC
LIMIT 10;
```

## ⚙️ Configuración de SQLite

### Pragmas Utilizados

```sql
PRAGMA foreign_keys = ON;           -- Integridad referencial
PRAGMA journal_mode = WAL;          -- Write-Ahead Logging
PRAGMA synchronous = NORMAL;        -- Balance seguridad/velocidad
PRAGMA cache_size = -8000;          -- 8MB de cache
```

**¿Por qué WAL (Write-Ahead Logging)?**

```
Modo Default (DELETE):
┌─────────┐
│ Lecturas│ → BLOQUEADAS durante escrituras
└─────────┘

Modo WAL:
┌─────────┐     ┌──────────┐
│ Lecturas│ ←→  │Escrituras│ → Concurrentes!
└─────────┘     └──────────┘
```

**Beneficios:**
- ✅ Lecturas no bloquean escrituras
- ✅ Escrituras no bloquean lecturas
- ✅ Mejor rendimiento en general
- ✅ Más robusto ante crashes

**Trade-off:**
- ⚠️ Genera archivo `-wal` adicional (temporal)

### Context Managers

Todas las operaciones usan context managers para garantizar transacciones correctas:

```python
# Implementación en bd/bdConector.py
@contextlib.contextmanager
def _cursor(self):
    conn = self._connect()
    try:
        cur = conn.cursor()
        yield cur
        conn.commit()  # Auto-commit si todo OK
    except sqlite3.Error as e:
        conn.rollback()  # Auto-rollback si error
        raise DatabaseError(f"Database error: {e}")
    finally:
        conn.close()  # Siempre cierra conexión
```

**Ejemplo de uso:**
```python
with self._cursor() as cur:
    cur.execute("INSERT INTO items (...) VALUES (?)", (data,))
    # Si llega aquí: commit automático
    # Si hay excepción: rollback automático
```

## 🔄 Operaciones Comunes

### Registrar una Venta Simple

```python
def record_sale(self, item_id, quantity):
    with self._cursor() as cur:
        # 1. Insertar venta
        cur.execute("INSERT INTO sells (item_id) VALUES (?)", (item_id,))
        sell_id = cur.lastrowid
        
        # 2. Obtener precio actual
        cur.execute("SELECT price, quantity FROM items WHERE id = ?", (item_id,))
        price, current_qty = cur.fetchone()
        
        # 3. Validar stock
        if current_qty < quantity:
            raise ValueError("Stock insuficiente")
        
        # 4. Insertar detalle
        cur.execute(
            "INSERT INTO details (sell_id, item_id, quantity, price) VALUES (?, ?, ?, ?)",
            (sell_id, item_id, quantity, price)
        )
        
        # 5. Actualizar stock
        cur.execute(
            "UPDATE items SET quantity = ? WHERE id = ?",
            (current_qty - quantity, item_id)
        )
    # Commit automático al salir del context manager
```

### Venta Múltiple (Bulk)

```python
def record_bulk_sale(self, items):
    # items = [{"item_id": 1, "quantity": 2}, {"item_id": 3, "quantity": 1}]
    with self._cursor() as cur:
        # 1. Crear venta
        cur.execute("INSERT INTO sells (item_id) VALUES (?)", (items[0]["item_id"],))
        sell_id = cur.lastrowid
        
        # 2. Para cada producto
        for item in items:
            item_id = item["item_id"]
            quantity = item["quantity"]
            
            # Obtener datos
            cur.execute("SELECT price, quantity FROM items WHERE id = ?", (item_id,))
            price, current_qty = cur.fetchone()
            
            # Validar stock
            if current_qty < quantity:
                raise ValueError(f"Stock insuficiente para item {item_id}")
            
            # Insertar detalle
            cur.execute(
                "INSERT INTO details (sell_id, item_id, quantity, price) VALUES (?, ?, ?, ?)",
                (sell_id, item_id, quantity, price)
            )
            
            # Actualizar stock
            cur.execute(
                "UPDATE items SET quantity = ? WHERE id = ?",
                (current_qty - quantity, item_id)
            )
    return sell_id
```

## 📊 Queries de Análisis

### Dashboard Stats

```sql
-- KPIs principales
SELECT
    (SELECT COUNT(*) FROM items WHERE status = 1) as total_productos,
    (SELECT COUNT(*) FROM items WHERE quantity <= min_quantity AND status = 1) as stock_bajo,
    (SELECT COUNT(*) FROM sells WHERE DATE(date) = DATE('now')) as ventas_hoy;
```

### Top 10 Productos

```sql
SELECT 
    i.id,
    i.name,
    i.barrs_code,
    SUM(d.quantity) as cantidad_vendida,
    SUM(d.quantity * d.price) as ingresos_generados
FROM details d
JOIN items i ON d.item_id = i.id
JOIN sells s ON d.sell_id = s.id
WHERE DATE(s.date) >= DATE('now', '-30 days')
GROUP BY i.id, i.name, i.barrs_code
ORDER BY cantidad_vendida DESC
LIMIT 10;
```

### Ventas por Día de la Semana

```sql
SELECT 
    CASE CAST(strftime('%w', date) AS INTEGER)
        WHEN 0 THEN 'Domingo'
        WHEN 1 THEN 'Lunes'
        WHEN 2 THEN 'Martes'
        WHEN 3 THEN 'Miércoles'
        WHEN 4 THEN 'Jueves'
        WHEN 5 THEN 'Viernes'
        WHEN 6 THEN 'Sábado'
    END as dia_semana,
    COUNT(*) as num_ventas
FROM sells
WHERE DATE(date) >= DATE('now', '-30 days')
GROUP BY strftime('%w', date)
ORDER BY num_ventas DESC;
```

## 🔧 Mantenimiento

### Backup de Base de Datos

```bash
# Backup simple (copiar archivo)
cp database.db database_backup_$(date +%Y%m%d).db

# Backup con SQLite (más seguro)
sqlite3 database.db ".backup database_backup_$(date +%Y%m%d).db"

# Backup programático desde Python
import sqlite3
import shutil

source = "database.db"
backup = f"database_backup_{datetime.now().strftime('%Y%m%d')}.db"
shutil.copy2(source, backup)
```

### Vacuum (Optimización)

```sql
-- Recuperar espacio después de muchos DELETEs
VACUUM;

-- O configurar auto-vacuum
PRAGMA auto_vacuum = INCREMENTAL;
PRAGMA incremental_vacuum(100);
```

### Verificar Integridad

```sql
PRAGMA integrity_check;
-- Resultado esperado: ok
```

### Analizar Rendimiento

```sql
EXPLAIN QUERY PLAN
SELECT * FROM items WHERE name LIKE '%laptop%';

-- Si ves SCAN TABLE: considera agregar índice
CREATE INDEX idx_items_name ON items(name);
```

## 🚨 Troubleshooting

### "database is locked"

**Causa**: Otra conexión tiene lock exclusivo

**Soluciones:**
1. Asegúrate de cerrar todas las conexiones
2. Usa WAL mode (ya configurado)
3. Aumenta timeout: `connection.execute("PRAGMA busy_timeout = 5000")`

### "unable to open database file"

**Causa**: Problemas de permisos o ruta incorrecta

**Soluciones:**
1. Verifica que el directorio exista y sea escribible
2. En producción, usa rutas de usuario (ver `bd/bdInstance.py`)
3. Verifica permisos: `ls -l database.db`

### Corrupción de Base de Datos

**Prevención:**
- ✅ Usa WAL mode
- ✅ `PRAGMA synchronous = NORMAL` o superior
- ✅ No kills forzados durante escrituras

**Recuperación:**
```sql
-- Verificar
PRAGMA integrity_check;

-- Si está corrupta, intentar dump/restore
sqlite3 database.db .dump > backup.sql
rm database.db
sqlite3 database.db < backup.sql
```

## 📚 Referencias

- [SQLite Oficial](https://www.sqlite.org/docs.html)
- [WAL Mode](https://www.sqlite.org/wal.html)
- [Implementación Local](../../bd/bdConector.py)

## 🔗 Ver También

- [Arquitectura](ARCHITECTURE.md) - Cómo se integra la BD
- [API](API.md) - Endpoints que usan la BD
- [Development](DEVELOPMENT.md) - Setup local
