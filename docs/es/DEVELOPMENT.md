# 🔧 Guía de Desarrollo

## 📋 Requisitos del Sistema

### Obligatorios

| Componente | Versión Mínima | Recomendada |
|------------|----------------|-------------|
| **Python** | 3.8+ | 3.13 |
| **pip** | 20.0+ | Latest |
| **Git** | 2.20+ | Latest |

### Opcionales (para desarrollo frontend)
- Node.js 18+ (si trabajas con assets)
- Editor con LSP Python (VSCode, PyCharm, etc.)

## 🚀 Setup Inicial (5 minutos)

### 1. Clonar Repositorio

```bash
git clone https://github.com/InnoDev69/StockManager.git
cd StockManager
```

### 2. Crear Entorno Virtual

```bash
# Linux/macOS
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

**¿Por qué venv?**  
Aísla dependencias del proyecto del sistema global, evitando conflictos.

### 3. Instalar Dependencias

```bash
pip install -r requirements.txt
```

**Dependencias principales:**
```
Flask==3.0.0              # Framework web
Werkzeug==3.0.1           # Utilidades y seguridad
python-dotenv==1.0.0      # Variables de entorno
pywebview                 # Ventana desktop
```

### 4. Configurar Variables de Entorno (Opcional)

Crea `.env` en la raíz del proyecto:

```env
# Seguridad
FLASK_SECRET_KEY=tu-clave-secreta-aleatoria-muy-larga

# Servidor
FLASK_PORT=5000
DEBUG=1

# Base de datos
DB_PATH=./bd/database.db
```

**⚠️ Importante:**  
- `FLASK_SECRET_KEY`: Usa una clave fuerte en producción
- `DEBUG=1`: Solo en desarrollo, NUNCA en producción

### 5. Verificar Instalación

```bash
python -c "import flask, werkzeug; print('✓ Instalación correcta')"
```

## ▶️ Ejecutar la Aplicación

### Opción A: Modo Desktop (Recomendado)

```bash
# Con venv activado
python main.py
```

Esto:
1. ✅ Inicia servidor Flask en puerto 5000
2. ✅ Crea ventana PyWebView
3. ✅ Carga interfaz automáticamente

**Salida esperada:**
```
[2024-01-15 10:30:00] INFO - Iniciando servidor en puerto 5000
[2024-01-15 10:30:01] INFO - Agregando tarea: _cleanup_old_logs cada 86400 segundos
[2024-01-15 10:30:01] INFO - Iniciando Scheduler
```

### Opción B: Solo Backend (Para desarrollo API)

```bash
# Inicia Flask sin PyWebView
export FLASK_APP=main.py
flask run --debug
```

Luego abre navegador en `http://127.0.0.1:5000`

**Ventajas:**
- ✅ Hot reload automático
- ✅ Debugging mejorado
- ✅ No requiere PyWebView

### Opción C: Con Debugger

```python
# En main.py, cambia la última línea:
if __name__ == "__main__":
    app.run(debug=True, use_reloader=True)
    # Comenta webview.start() para desarrollo
```

## 📁 Estructura del Proyecto

```
StockManager/
├── main.py                 # ⭐ Entrypoint principal
├── requirements.txt        # Dependencias Python
├── .env                    # Variables de entorno (crear)
├── .gitignore              # Archivos ignorados por git
│
├── api/
│   └── API.py             # 🔌 Blueprint REST API
│
├── bd/                     # 💾 Capa de base de datos
│   ├── bdConector.py      # Conector SQLite
│   ├── bdInstance.py      # Instancia global
│   ├── bdErrors.py        # Excepciones custom
│   └── database.db        # BD SQLite (se crea automáticamente)
│
├── data/                   # ✅ Validación y límites
│   ├── validators.py      # Validadores de input
│   └── limits.py          # Constantes de límites
│
├── tools/                  # 🛠️ Utilidades
│   ├── logger.py          # Sistema de logging
│   ├── scheduler.py       # Tareas periódicas
│   └── timmer.py          # Medición de rendimiento
│
├── templates/              # 🎨 Plantillas HTML (Jinja2)
│   ├── base.html          # Template base
│   ├── dashboard.html     # Dashboard principal
│   ├── login.html         # Login/Registro
│   └── ...
│
├── static/                 # 📦 Assets estáticos
│   ├── css/
│   │   └── style.css      # Estilos principales
│   ├── js/
│   │   ├── app.js         # JavaScript principal
│   │   └── notifications.js
│   └── app/
│       ├── icon.png       # Ícono de aplicación
│       └── icon.ico
│
├── logs/                   # 📋 Logs de aplicación (se crea automáticamente)
│   └── app_YYYYMMDD.log
│
└── docs/                   # 📚 Documentación
    ├── es/
    └── en/
```

### Archivos Clave para Desarrollo

| Archivo | Propósito | Cuándo Modificar |
|---------|-----------|------------------|
| `main.py` | Rutas UI y configuración Flask | Agregar rutas HTML nuevas |
| `api/API.py` | Endpoints REST | Agregar endpoints JSON |
| `bd/bdConector.py` | Operaciones de BD | Agregar queries/operaciones |
| `data/validators.py` | Validación | Agregar reglas de validación |
| `templates/*.html` | Interfaz | Cambiar UI |
| `static/js/app.js` | Lógica frontend | Interactividad |

## 🔨 Tareas Comunes de Desarrollo

### Agregar Nueva Ruta UI

```python
# En main.py
@app.route("/nueva-ruta")
def nueva_ruta():
    """Descripción de la ruta."""
    if not session.get("user_id"):
        return redirect("/login")
    
    # Tu lógica aquí
    data = db.execute_query("SELECT * FROM ...")
    
    return render_template("nueva_template.html", data=data)
```

### Agregar Endpoint API

```python
# En api/API.py
@api_bp.route("/nuevo-endpoint", methods=["GET"])
def nuevo_endpoint():
    """Documentación del endpoint."""
    auth_error = require_auth()
    if auth_error:
        return auth_error
    
    # Tu lógica aquí
    data = db.execute_query("SELECT * FROM ...")
    
    return jsonify({"data": data}), 200
```

### Agregar Tabla a BD

```python
# En bd/bdConector.py, método init_db():
new_table_query = """
CREATE TABLE IF NOT EXISTS nueva_tabla (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campo TEXT NOT NULL,
    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""
cur.execute(new_table_query)
```

### Agregar Validador

```python
# En data/validators.py
class NuevoValidator:
    @staticmethod
    def validate(campo1, campo2):
        return {
            "campo1": Validator.validate_string("Campo 1", campo1, 50),
            "campo2": Validator.validate_number("Campo 2", campo2, min_val=0)
        }
```

## 🧪 Testing y Debugging

### Verificar Conexión a BD

```python
from bd.bdInstance import db

# En consola Python o script
rows = db.execute_query("SELECT * FROM users LIMIT 1")
print(rows)
```

### Ver Logs en Tiempo Real

```bash
# Linux/macOS
tail -f logs/app_$(date +%Y%m%d).log

# Windows PowerShell
Get-Content logs/app_$(Get-Date -Format "yyyyMMdd").log -Wait -Tail 10
```

### Probar Endpoints API

```bash
# Health check
curl http://localhost:5000/api/health

# Con sesión (después de login)
curl -b cookies.txt http://localhost:5000/api/products
```

### Debugging con VSCode

Crea `.vscode/launch.json`:

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

## 🔧 Variables de Entorno

### Descripción Completa

| Variable | Tipo | Default | Descripción |
|----------|------|---------|-------------|
| `FLASK_SECRET_KEY` | string | `"a"` | Clave para firmar cookies de sesión. ⚠️ Cambiar en producción |
| `FLASK_PORT` | int | `5000` | Puerto donde escucha Flask |
| `DEBUG` | bool | `0` | Habilita features de debug en templates |
| `DB_PATH` | string | `./bd/database.db` | Ruta de base de datos en desarrollo |

### Generar FLASK_SECRET_KEY Segura

```python
import secrets
print(secrets.token_hex(32))
# Copia el resultado a .env
```

## 📊 Logs y Monitoreo

### Niveles de Log

```python
from tools.logger import logger

logger.debug("Información detallada para debugging")
logger.info("Operación normal, información")
logger.warning("Advertencia, algo inesperado")
logger.error("Error, operación falló")
logger.exception("Error con stack trace completo")
```

### Ubicación de Logs

- **Desarrollo**: `./logs/app_YYYYMMDD.log`
- **Producción Windows**: `%APPDATA%/StockManager/logs/`
- **Producción Linux/Mac**: `~/.stock_manager/logs/`

### Limpieza Automática

Los logs más antiguos de 3 días se eliminan automáticamente (configurado en `tools/logger.py`).

## 🐛 Troubleshooting Común

### "ModuleNotFoundError: No module named 'flask'"

**Solución:**
```bash
# Asegúrate de que venv esté activado
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Reinstala dependencias
pip install -r requirements.txt
```

### "database is locked"

**Solución:**
1. Cierra otras conexiones a la BD
2. Verifica que no haya otro proceso de Python corriendo
3. Reinicia la aplicación

### Puerto 5000 ya en uso

**Solución 1:** Cambiar puerto
```bash
export FLASK_PORT=5001
python main.py
```

**Solución 2:** Ver qué usa el puerto
```bash
# Linux/macOS
lsof -i :5000

# Windows
netstat -ano | findstr :5000
```

### "Template not found"

**Verificar:**
1. ¿Existe el archivo en `templates/`?
2. ¿El nombre es correcto (case-sensitive)?
3. ¿Flask app tiene configurado `template_folder`?

```python
# En main.py
app = Flask(__name__, 
            template_folder="templates",  # ← Verificar
            static_folder="static")
```

### Cambios no se reflejan

**Si modificas Python:**
- Reinicia la aplicación completa

**Si modificas templates/HTML:**
```python
# Habilita auto-reload
app.config['TEMPLATES_AUTO_RELOAD'] = True
```

**Si modificas CSS/JS:**
- Limpia caché del navegador (Ctrl+F5)
- O agrega versioning:
```html
<link rel="stylesheet" href="/static/css/style.css?v=2">
```

## 🎯 Mejores Prácticas

### Para Código Python

1. ✅ **Usa type hints**
```python
def get_user(user_id: int) -> dict:
    return db.execute_query("SELECT * FROM users WHERE id = ?", (user_id,))
```

2. ✅ **Valida inputs siempre**
```python
try:
    data = ItemValidator.validate(...)
except ValidationError as e:
    return render_template("form.html", error=e.message)
```

3. ✅ **Usa context managers para BD**
```python
with db._cursor() as cur:
    cur.execute(...)
```

4. ✅ **Loggea operaciones importantes**
```python
logger.info(f"Usuario {user_id} registró venta #{sale_id}")
```

### Para Frontend

1. ✅ **Valida en cliente Y servidor**
2. ✅ **Usa fetch API para AJAX**
3. ✅ **Maneja errores gracefully**
4. ✅ **Muestra feedback al usuario**

### Para Git

1. ✅ **Commits atómicos y descriptivos**
```bash
git commit -m "feat: Add product search by barcode"
```

2. ✅ **No commitees archivos sensibles**
- `.env`
- `database.db`
- `logs/`
- `__pycache__/`

3. ✅ **Usa branches para features**
```bash
git checkout -b feature/nueva-funcionalidad
```

## 🔗 Próximos Pasos

- 📖 Lee [ARCHITECTURE.md](ARCHITECTURE.md) para entender el diseño
- 🔌 Explora [API.md](API.md) para ver endpoints disponibles
- 💾 Revisa [DATABASE.md](DATABASE.md) para el esquema de datos
- 🚀 Consulta [DEPLOYMENT.md](DEPLOYMENT.md) para empaquetar

## 💡 Tips Pro

1. **Usa watchdog para auto-reload**
```bash
pip install watchdog
watchmedo auto-restart --patterns="*.py" --recursive python main.py
```

2. **SQLite Browser para ver BD**
```bash
# Instalar DB Browser for SQLite
# https://sqlitebrowser.org/
```

3. **Flask Shell para experimentos**
```bash
export FLASK_APP=main.py
flask shell
>>> from bd.bdInstance import db
>>> db.execute_query("SELECT * FROM users")
```

4. **Profiling de rendimiento**
```python
from tools.timmer import measure_time

@measure_time
def funcion_lenta():
    # código...
```
