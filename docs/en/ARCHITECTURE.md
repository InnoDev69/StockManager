# StockManager Architecture

## Executive Summary

StockManager is a hybrid desktop application that combines:
- **Frontend**: Native desktop application using PyWebView
- **Backend**: Flask server running locally
- **Database**: SQLite for local persistence

This architecture provides a native desktop experience while leveraging the flexibility of web development.

## Design Decisions

### Why PyWebView?

**Advantages:**
- Executable size: ~20MB vs 150MB+ with Electron
- Memory consumption: Uses system browser
- Simplicity: All in Python, no Node.js required
- Performance: Lower overhead, faster startup

**Trade-offs:**
- Requires system WebView (generally available)
- Less control over rendering engine

### Why Flask?

- Simplicity and mature ecosystem
- Native Jinja2 template support
- Built-in sessions without additional configuration
- Ideal for traditional CRUD applications

## Main Components

### 1. PyWebView (Desktop Shell)

```
┌─────────────────────────────────────┐
│      PyWebView Window               │
│  ┌───────────────────────────────┐  │
│  │   System Browser (WebView)    │  │
│  │   ┌─────────────────────────┐ │  │
│  │   │  Web UI (HTML/CSS)      │ │  │
│  │   │  JavaScript (Vanilla)   │ │  │
│  │   └─────────────────────────┘ │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
           ↕ HTTP
    http://127.0.0.1:5000
```

**Responsibilities:**
- Create native application window
- Start Flask server in background
- Manage application lifecycle
- Provide native icon and menus

**Key files:**
- `main.py` (lines 686-698): Window configuration

### 2. Flask Server (Backend + UI)

```
┌────────────────────────────────────────┐
│         Flask Application              │
├────────────────────────────────────────┤
│                                        │
│  ┌──────────────┐    ┌──────────────┐ │
│  │   UI Routes  │    │   REST API   │ │
│  │   (Views)    │    │  (/api/*)    │ │
│  └──────┬───────┘    └──────┬───────┘ │
│         │                   │          │
│    ┌────▼──────┐     ┌──────▼─────┐   │
│    │ Templates │     │   JSON     │   │
│    │  (Jinja2) │     │ Responses  │   │
│    └───────────┘     └────────────┘   │
│                                        │
└────────────────────────────────────────┘
```

**UI Routes** (`main.py`):
- `/` - Main dashboard
- `/login` - Authentication
- `/products/new` - Product form
- `/sales/new` - Sales registration
- `/settings` - User settings

**REST API** (`api/API.py`):
- All under `/api` prefix
- JSON format
- Session-based authentication

### 3. Persistence Layer (SQLite)

```
┌────────────────────────────────────┐
│   BDConector (bd/bdConector.py)    │
├────────────────────────────────────┤
│  • Context Managers                │
│  • Automatic Transactions          │
│  • Parameterized Queries           │
│  • Connection Pooling (WAL mode)   │
└────────────────────────────────────┘
           ↕
┌────────────────────────────────────┐
│         SQLite Database             │
│  • Mode: WAL (Write-Ahead Logging) │
│  • Foreign Keys: ENABLED            │
│  • Auto-vacuum: INCREMENTAL         │
└────────────────────────────────────┘
```

**Optimizations:**
- `PRAGMA journal_mode = WAL` - Concurrent reads
- `PRAGMA synchronous = NORMAL` - Performance/safety balance
- `PRAGMA cache_size = -8000` - 8MB cache
- Context managers for safe transactions

### 4. Validation System

```
┌────────────────────────────────────┐
│    Request (Form/JSON)              │
└────────────┬───────────────────────┘
             │
             ▼
┌────────────────────────────────────┐
│    Validator (data/validators.py)  │
│  • validate_string()                │
│  • validate_number()                │
│  • ItemValidator                    │
│  • UserValidator                    │
└────────────┬───────────────────────┘
             │
             ▼ (ValidationError)
┌────────────────────────────────────┐
│    Limits (data/limits.py)         │
│  • ITEM_NAME_MAX = 25               │
│  • USER_PASSWORD_MAX = 128          │
│  • etc.                             │
└────────────────────────────────────┘
```

**Principles:**
- Backend validation (never trust client)
- Descriptive error messages
- Centralized limits
- Type-safe where possible

### 5. Logging System

```
┌────────────────────────────────────┐
│      AppLogger (Singleton)          │
├────────────────────────────────────┤
│  Console Handler (WARNING+)        │
│  File Handler (DEBUG+)              │
│  • Daily rotation                   │
│  • Automatic cleanup (3 days)      │
│  • Format: [timestamp] LEVEL - msg │
└────────────────────────────────────┘
```

**Log locations:**
- Development: `./logs/app_YYYYMMDD.log`
- Production Windows: `%APPDATA%/StockManager/logs/`
- Production Linux/Mac: `~/.stock_manager/logs/`

## Execution Flow

### Application Startup

```
1. User executes StockManager
        ↓
2. main.py starts
        ↓
3. db.init_db() - Create/validate SQLite tables
        ↓
4. SCHEDULER.start() - Start periodic tasks
        ↓
5. webview.create_window() - Create PyWebView window
        ↓
6. Flask app starts on http://127.0.0.1:5000
        ↓
7. PyWebView loads server URL
        ↓
8. User sees web interface in native window
```

### Processing a Sale

```
1. User enters barcode in /sales/new
        ↓
2. POST /sales → sale_new() in main.py
        ↓
3. Input validation (barcode, quantity)
        ↓
4. db.get_item_by_barcode(barcode)
        ↓
5. Check available stock
        ↓
6. db.record_sale(item_id, qty)
   ├─ INSERT INTO sells
   ├─ INSERT INTO details
   └─ UPDATE items SET quantity = quantity - qty
        ↓
7. COMMIT (automatic transaction)
        ↓
8. flash("Sale registered")
        ↓
9. Redirect to dashboard with success message
```

**Error handling:**
- Insufficient stock → Rollback + message
- Product not found → 404 + message
- DB error → Automatic rollback + log

## Authentication and Session

### Login Flow

```
┌──────────────┐
│  GET /login  │
│  (HTML form) │
└──────┬───────┘
       │
       ▼
┌──────────────────┐
│  POST /login     │
│  user + password │
└──────┬───────────┘
       │
       ▼
┌─────────────────────────────┐
│  db.execute_query()         │
│  SELECT id, password, role  │
│  FROM users WHERE username  │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│  check_password_hash()      │
│  (Werkzeug PBKDF2:SHA256)   │
└──────┬──────────────────────┘
       │
       ▼ (valid)
┌─────────────────────────────┐
│  session["user_id"] = id    │
│  session["username"] = user │
│  session["role"] = role     │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│  Cookie signed with         │
│  FLASK_SECRET_KEY           │
└─────────────────────────────┘
```

**Security:**
- Hashed passwords (never plain text)
- Signed cookies (prevents tampering)
- `SameSite=Lax` (basic CSRF protection)
- Session timeout: 30 minutes

### Authorization Guards

```python
# For UI routes
if not session.get("user_id"):
    return redirect("/login")

# For API
def require_auth():
    if not session.get("user_id"):
        return jsonify({"error": "Unauthorized"}), 401
    return None

# For admin routes
if session.get("role") != "admin":
    return redirect(url_for("index"))
```

## Data Model

```
┌─────────────┐
│   users     │
├─────────────┤
│ id (PK)     │
│ username ◄──┐
│ password    │
│ email       │
│ role        │
└─────────────┘

┌─────────────────┐         ┌──────────────┐
│     items       │         │    sells     │
├─────────────────┤         ├──────────────┤
│ id (PK)      ◄──┼─────────┤ item_id (FK) │
│ barrs_code      │         │ id (PK)   ◄──┼─┐
│ name            │         │ date         │ │
│ description     │         └──────────────┘ │
│ quantity        │                          │
│ min_quantity    │         ┌──────────────┐ │
│ price           │         │   details    │ │
│ status          │         ├──────────────┤ │
└─────────────────┘         │ id (PK)      │ │
                            │ sell_id (FK) ├─┘
                            │ item_id (FK) │
                            │ quantity     │
                            │ price        │
                            └──────────────┘
```

See [DATABASE.md](DATABASE.md) for complete schema details.

## Technology Stack

### Backend
- **Python 3.8+**: Main language
- **Flask 3.0.0**: Web framework
- **SQLite 3**: Database
- **Werkzeug 3.0.1**: Utilities and security
- **python-dotenv**: Environment variables
- **PyWebView**: Desktop wrapper

### Frontend
- **HTML5 + Jinja2**: Templates
- **CSS3**: Styles (vanilla)
- **JavaScript (ES6+)**: Interactivity without frameworks
- **Fetch API**: Backend communication

## Implemented Optimizations

### Database
- **WAL Mode**: Concurrent reads without blocking
- **Connection Pooling**: Connection reuse
- **Prepared Statements**: SQL injection prevention
- **Transaction Management**: Automatic commit/rollback

### Application
- **Session-based Auth**: Faster than JWT for desktop
- **Template Caching**: Enabled Jinja2 cache
- **Static Asset Serving**: Optimized Flask
- **Lazy Loading**: Data loaded on demand

### Frontend
- **Vanilla JS**: No framework overhead
- **Fetch API**: Modern and performant
- **CSS Grid/Flexbox**: Responsive layout
- **Local Storage**: UI preferences cache

## Cross References

- [Development Guide](DEVELOPMENT.md) - Setup and configuration
- [REST API](API.md) - Endpoints and examples
- [Database](DATABASE.md) - Schema and queries
- [Security](SECURITY_ROLES.md) - Roles and permissions
- [Deployment](DEPLOYMENT.md) - Packaging and distribution

## Best Practices

### For Developers

1. **Always use context managers** for DB operations
2. **Validate on backend** even with frontend validation
3. **Use prepared statements** for all queries
4. **Log critical operations** (sales, stock changes)
5. **Handle exceptions** and return useful errors

### For Maintenance

1. **Regular backup** of database.db
2. **Monitor logs** to detect issues early
3. **Test migrations** in staging environment
4. **Document schema changes** in DATABASE.md
5. **Use git tags** for releases
