# Development Guide

## System Requirements

### Required

| Component | Minimum Version | Recommended |
|-----------|-----------------|-------------|
| **Python** | 3.8+ | 3.13 |
| **pip** | 20.0+ | Latest |
| **Git** | 2.20+ | Latest |

### Optional (for frontend development)
- Node.js 18+ (if working with assets)
- Editor with Python LSP (VSCode, PyCharm, etc.)

## Initial Setup (5 minutes)

### 1. Clone Repository

```bash
git clone https://github.com/InnoDev69/StockManager.git
cd StockManager
```

### 2. Create Virtual Environment

```bash
# Linux/macOS
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

**Why venv?**  
Isolates project dependencies from global system, avoiding conflicts.

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

**Main dependencies:**
```
Flask==3.0.0              # Web framework
Werkzeug==3.0.1           # Utilities and security
python-dotenv==1.0.0      # Environment variables
pywebview                 # Desktop window
```

### 4. Configure Environment Variables (Optional)

Create `.env` in project root:

```env
# Security
FLASK_SECRET_KEY=your-very-long-random-secret-key

# Server
FLASK_PORT=5000
DEBUG=1

# Database
DB_PATH=./bd/database.db
```

**Important:**  
- `FLASK_SECRET_KEY`: Use strong key in production
- `DEBUG=1`: Development only, NEVER in production

### 5. Verify Installation

```bash
python -c "import flask, werkzeug; print('Installation OK')"
```

## Running the Application

### Option A: Desktop Mode (Recommended)

```bash
# With venv activated
python main.py
```

This:
1. Starts Flask server on port 5000
2. Creates PyWebView window
3. Loads interface automatically

**Expected output:**
```
[2024-01-15 10:30:00] INFO - Starting server on port 5000
[2024-01-15 10:30:01] INFO - Adding task: _cleanup_old_logs every 86400 seconds
[2024-01-15 10:30:01] INFO - Starting Scheduler
```

### Option B: Backend Only (For API development)

```bash
# Start Flask without PyWebView
export FLASK_APP=main.py
flask run --debug
```

Then open browser at `http://127.0.0.1:5000`

**Advantages:**
- Automatic hot reload
- Improved debugging
- PyWebView not required

### Option C: With Debugger

```python
# In main.py, change last line:
if __name__ == "__main__":
    app.run(debug=True, use_reloader=True)
    # Comment out webview.start() for development
```

## Project Structure

```
StockManager/
├── main.py                 # Main entrypoint
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables (create)
├── .gitignore              # Git ignored files
│
├── api/
│   └── API.py             # REST API Blueprint
│
├── bd/                     # Database layer
│   ├── bdConector.py      # SQLite connector
│   ├── bdInstance.py      # Global instance
│   ├── bdErrors.py        # Custom exceptions
│   └── database.db        # SQLite DB (auto-created)
│
├── data/                   # Validation and limits
│   ├── validators.py      # Input validators
│   └── limits.py          # Limit constants
│
├── tools/                  # Utilities
│   ├── logger.py          # Logging system
│   ├── scheduler.py       # Periodic tasks
│   └── timmer.py          # Performance measurement
│
├── templates/              # HTML templates (Jinja2)
│   ├── base.html          # Base template
│   ├── dashboard.html     # Main dashboard
│   ├── login.html         # Login/Register
│   └── ...
│
├── static/                 # Static assets
│   ├── css/
│   │   └── style.css      # Main styles
│   ├── js/
│   │   ├── app.js         # Main JavaScript
│   │   └── notifications.js
│   └── app/
│       ├── icon.png       # Application icon
│       └── icon.ico
│
├── logs/                   # Application logs (auto-created)
│   └── app_YYYYMMDD.log
│
└── docs/                   # Documentation
    ├── es/
    └── en/
```

### Key Files for Development

| File | Purpose | When to Modify |
|------|---------|----------------|
| `main.py` | UI routes and Flask config | Add new HTML routes |
| `api/API.py` | REST endpoints | Add JSON endpoints |
| `bd/bdConector.py` | DB operations | Add queries/operations |
| `data/validators.py` | Validation | Add validation rules |
| `templates/*.html` | Interface | Change UI |
| `static/js/app.js` | Frontend logic | Interactivity |

## Common Development Tasks

### Add New UI Route

```python
# In main.py
@app.route("/new-route")
def new_route():
    """Route description."""
    if not session.get("user_id"):
        return redirect("/login")
    
    # Your logic here
    data = db.execute_query("SELECT * FROM ...")
    
    return render_template("new_template.html", data=data)
```

### Add API Endpoint

```python
# In api/API.py
@api_bp.route("/new-endpoint", methods=["GET"])
def new_endpoint():
    """Endpoint documentation."""
    auth_error = require_auth()
    if auth_error:
        return auth_error
    
    # Your logic here
    data = db.execute_query("SELECT * FROM ...")
    
    return jsonify({"data": data}), 200
```

### Add DB Table

```python
# In bd/bdConector.py, init_db() method:
new_table_query = """
CREATE TABLE IF NOT EXISTS new_table (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    field TEXT NOT NULL,
    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""
cur.execute(new_table_query)
```

### Add Validator

```python
# In data/validators.py
class NewValidator:
    @staticmethod
    def validate(field1, field2):
        return {
            "field1": Validator.validate_string("Field 1", field1, 50),
            "field2": Validator.validate_number("Field 2", field2, min_val=0)
        }
```

## Testing and Debugging

### Verify DB Connection

```python
from bd.bdInstance import db

# In Python console or script
rows = db.execute_query("SELECT * FROM users LIMIT 1")
print(rows)
```

### View Logs in Real Time

```bash
# Linux/macOS
tail -f logs/app_$(date +%Y%m%d).log

# Windows PowerShell
Get-Content logs/app_$(Get-Date -Format "yyyyMMdd").log -Wait -Tail 10
```

### Test API Endpoints

```bash
# Health check
curl http://localhost:5000/api/health

# With session (after login)
curl -b cookies.txt http://localhost:5000/api/products
```

### Debugging with VSCode

Create `.vscode/launch.json`:

```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: Flask",
            "type": "python",
            "request": "launch",
            "module": "flask",
            "env": {
                "FLASK_APP": "main.py",
                "FLASK_DEBUG": "1"
            },
            "args": [
                "run",
                "--no-debugger",
                "--no-reload"
            ],
            "jinja": true
        }
    ]
}
```

## Environment Variables

### Complete Description

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `FLASK_SECRET_KEY` | string | `"a"` | Key to sign session cookies. Change in production |
| `FLASK_PORT` | int | `5000` | Port where Flask listens |
| `DEBUG` | bool | `0` | Enables debug features in templates |
| `DB_PATH` | string | `./bd/database.db` | Database path in development |

### Generate Secure FLASK_SECRET_KEY

```python
import secrets
print(secrets.token_hex(32))
# Copy result to .env
```

## Logs and Monitoring

### Log Levels

```python
from tools.logger import logger

logger.debug("Detailed information for debugging")
logger.info("Normal operation, information")
logger.warning("Warning, something unexpected")
logger.error("Error, operation failed")
logger.exception("Error with complete stack trace")
```

### Log Location

- **Development**: `./logs/app_YYYYMMDD.log`
- **Production Windows**: `%APPDATA%/StockManager/logs/`
- **Production Linux/Mac**: `~/.stock_manager/logs/`

### Automatic Cleanup

Logs older than 3 days are automatically deleted (configured in `tools/logger.py`).

## Common Troubleshooting

### "ModuleNotFoundError: No module named 'flask'"

**Solution:**
```bash
# Ensure venv is activated
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Reinstall dependencies
pip install -r requirements.txt
```

### "database is locked"

**Solution:**
1. Close other DB connections
2. Verify no other Python process is running
3. Restart application

### Port 5000 already in use

**Solution 1:** Change port
```bash
export FLASK_PORT=5001
python main.py
```

**Solution 2:** See what's using the port
```bash
# Linux/macOS
lsof -i :5000

# Windows
netstat -ano | findstr :5000
```

### "Template not found"

**Verify:**
1. Does file exist in `templates/`?
2. Is name correct (case-sensitive)?
3. Does Flask app have `template_folder` configured?

```python
# In main.py
app = Flask(__name__, 
            template_folder="templates",  # Check this
            static_folder="static")
```

### Changes not reflected

**If modifying Python:**
- Restart complete application

**If modifying templates/HTML:**
```python
# Enable auto-reload
app.config['TEMPLATES_AUTO_RELOAD'] = True
```

**If modifying CSS/JS:**
- Clear browser cache (Ctrl+F5)
- Or add versioning:
```html
<link rel="stylesheet" href="/static/css/style.css?v=2">
```

## Best Practices

### For Python Code

1. **Use type hints**
```python
def get_user(user_id: int) -> dict:
    return db.execute_query("SELECT * FROM users WHERE id = ?", (user_id,))
```

2. **Always validate inputs**
```python
try:
    data = ItemValidator.validate(...)
except ValidationError as e:
    return render_template("form.html", error=e.message)
```

3. **Use context managers for DB**
```python
with db._cursor() as cur:
    cur.execute(...)
```

4. **Log important operations**
```python
logger.info(f"User {user_id} registered sale #{sale_id}")
```

### For Frontend

1. **Validate on client AND server**
2. **Use fetch API for AJAX**
3. **Handle errors gracefully**
4. **Show feedback to user**

### For Git

1. **Atomic and descriptive commits**
```bash
git commit -m "feat: Add product search by barcode"
```

2. **Don't commit sensitive files**
- `.env`
- `database.db`
- `logs/`
- `__pycache__/`

3. **Use branches for features**
```bash
git checkout -b feature/new-functionality
```

## Next Steps

- Read [ARCHITECTURE.md](ARCHITECTURE.md) to understand design
- Explore [API.md](API.md) to see available endpoints
- Review [DATABASE.md](DATABASE.md) for data schema
- Consult [DEPLOYMENT.md](DEPLOYMENT.md) to package

## Pro Tips

1. **Use watchdog for auto-reload**
```bash
pip install watchdog
watchmedo auto-restart --patterns="*.py" --recursive python main.py
```

2. **SQLite Browser to view DB**
```bash
# Install DB Browser for SQLite
# https://sqlitebrowser.org/
```

3. **Flask Shell for experiments**
```bash
export FLASK_APP=main.py
flask shell
>>> from bd.bdInstance import db
>>> db.execute_query("SELECT * FROM users")
```

4. **Performance profiling**
```python
from tools.timmer import measure_time

@measure_time
def slow_function():
    # code...
```
