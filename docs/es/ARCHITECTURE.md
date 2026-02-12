# 🏗️ Arquitectura de StockManager

## 📋 Resumen Ejecutivo

StockManager es una aplicación de escritorio híbrida que combina:
- **Frontend**: Aplicación desktop nativa usando PyWebView
- **Backend**: Servidor Flask ejecutándose localmente
- **Base de Datos**: SQLite para persistencia local

Esta arquitectura permite ofrecer una experiencia de escritorio nativa mientras se aprovecha la flexibilidad del desarrollo web.

## 🎯 Decisiones de Diseño

### ¿Por qué PyWebView?

**Ventajas:**
- ✅ **Tamaño del ejecutable**: ~20MB vs 150MB+ con Electron
- ✅ **Consumo de memoria**: Usa el navegador del sistema
- ✅ **Simplicidad**: Todo en Python, sin necesidad de Node.js
- ✅ **Rendimiento**: Menor overhead, inicio más rápido

**Trade-offs:**
- ⚠️ Requiere WebView del sistema (generalmente disponible)
- ⚠️ Menos control sobre el motor de rendering

### ¿Por qué Flask?

- ✅ Simplicidad y madurez del ecosistema
- ✅ Soporte nativo de plantillas Jinja2
- ✅ Sesiones integradas sin configuración adicional
- ✅ Ideal para aplicaciones CRUD tradicionales

## 🔧 Componentes Principales

### 1. PyWebView (Desktop Shell)

```
┌─────────────────────────────────────┐
│      PyWebView Window               │
│  ┌───────────────────────────────┐  │
│  │   Navegador Sistema (WebView)  │  │
│  │   ┌─────────────────────────┐  │  │
│  │   │  Interfaz Web (HTML/CSS) │  │  │
│  │   │  JavaScript (Vanilla)    │  │  │
│  │   └─────────────────────────┘  │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
           ↕ HTTP
    http://127.0.0.1:5000
```

**Responsabilidades:**
- Crear ventana nativa de la aplicación
- Iniciar servidor Flask en segundo plano
- Gestionar ciclo de vida de la aplicación
- Proporcionar ícono y menús nativos

**Archivos clave:**
- `main.py` (líneas 686-698): Configuración de ventana

### 2. Servidor Flask (Backend + UI)

```
┌────────────────────────────────────────┐
│         Flask Application              │
├────────────────────────────────────────┤
│                                        │
│  ┌──────────────┐    ┌──────────────┐ │
│  │   Rutas UI   │    │   API REST   │ │
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

**Rutas UI** (`main.py`):
- `/` - Dashboard principal
- `/login` - Autenticación
- `/products/new` - Formulario de productos
- `/sales/new` - Registro de ventas
- `/settings` - Configuración de usuario

**API REST** (`api/API.py`):
- Todas bajo prefix `/api`
- Formato JSON
- Autenticación basada en sesión

### 3. Capa de Persistencia (SQLite)

```
┌────────────────────────────────────┐
│      BDConector (bd/bdConector.py) │
├────────────────────────────────────┤
│  • Context Managers                │
│  • Transacciones Automáticas       │
│  • Queries Parametrizadas          │
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

**Optimizaciones:**
- `PRAGMA journal_mode = WAL` - Lecturas concurrentes
- `PRAGMA synchronous = NORMAL` - Balance rendimiento/seguridad
- `PRAGMA cache_size = -8000` - 8MB de cache
- Context managers para transacciones seguras

### 4. Sistema de Validación

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
│    Límites (data/limits.py)        │
│  • ITEM_NAME_MAX = 25               │
│  • USER_PASSWORD_MAX = 128          │
│  • etc.                             │
└────────────────────────────────────┘
```

**Principios:**
- Validación en backend (never trust client)
- Mensajes de error descriptivos
- Límites centralizados
- Type-safe donde sea posible

### 5. Sistema de Logging

```
┌────────────────────────────────────┐
│      AppLogger (Singleton)          │
├────────────────────────────────────┤
│  Console Handler (WARNING+)        │
│  File Handler (DEBUG+)              │
│  • Rotación diaria                  │
│  • Limpieza automática (3 días)    │
│  • Formato: [timestamp] LEVEL - msg │
└────────────────────────────────────┘
```

**Ubicación de logs:**
- Desarrollo: `./logs/app_YYYYMMDD.log`
- Producción Windows: `%APPDATA%/StockManager/logs/`
- Producción Linux/Mac: `~/.stock_manager/logs/`

## 🔄 Flujo de Ejecución

### Inicio de la Aplicación

```
1. Usuario ejecuta StockManager
        ↓
2. main.py inicia
        ↓
3. db.init_db() - Crea/valida tablas SQLite
        ↓
4. SCHEDULER.start() - Inicia tareas periódicas
        ↓
5. webview.create_window() - Crea ventana PyWebView
        ↓
6. Flask app inicia en http://127.0.0.1:5000
        ↓
7. PyWebView carga URL del servidor
        ↓
8. Usuario ve interfaz web en ventana nativa
```

### Procesamiento de una Venta

```
1. Usuario ingresa código de barras en /sales/new
        ↓
2. POST /sales → sale_new() en main.py
        ↓
3. Validación de entrada (barcode, quantity)
        ↓
4. db.get_item_by_barcode(barcode)
        ↓
5. Verificación de stock disponible
        ↓
6. db.record_sale(item_id, qty)
   ├─ INSERT INTO sells
   ├─ INSERT INTO details
   └─ UPDATE items SET quantity = quantity - qty
        ↓
7. COMMIT (transacción automática)
        ↓
8. flash("Venta registrada")
        ↓
9. Redirect a dashboard con mensaje de éxito
```

**Manejo de errores:**
- Stock insuficiente → Rollback + mensaje
- Producto no existe → 404 + mensaje
- Error DB → Rollback automático + log

## 🔐 Autenticación y Sesión

### Flujo de Login

```
┌──────────────┐
│  GET /login  │
│  (form HTML) │
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
       ▼ (válido)
┌─────────────────────────────┐
│  session["user_id"] = id    │
│  session["username"] = user │
│  session["role"] = role     │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│  Cookie firmada con         │
│  FLASK_SECRET_KEY           │
└─────────────────────────────┘
```

**Seguridad:**
- Contraseñas hasheadas (nunca texto plano)
- Cookies firmadas (previene tampering)
- `SameSite=Lax` (protección CSRF básica)
- Timeout de sesión: 30 minutos

### Guards de Autorización

```python
# Para rutas UI
if not session.get("user_id"):
    return redirect("/login")

# Para API
def require_auth():
    if not session.get("user_id"):
        return jsonify({"error": "No autorizado"}), 401
    return None

# Para rutas admin
if session.get("role") != "admin":
    return redirect(url_for("index"))
```

## 📊 Modelo de Datos

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

Ver [DATABASE.md](DATABASE.md) para detalles completos del esquema.

## 🎨 Stack Tecnológico

### Backend
- **Python 3.8+**: Lenguaje principal
- **Flask 3.0.0**: Framework web
- **SQLite 3**: Base de datos
- **Werkzeug 3.0.1**: Utilidades y seguridad
- **python-dotenv**: Variables de entorno
- **PyWebView**: Wrapper desktop

### Frontend
- **HTML5 + Jinja2**: Templates
- **CSS3**: Estilos (vanilla)
- **JavaScript (ES6+)**: Interactividad sin frameworks
- **Fetch API**: Comunicación con backend

## 🚀 Optimizaciones Implementadas

### Base de Datos
✅ **WAL Mode**: Lecturas concurrentes sin bloqueo  
✅ **Connection Pooling**: Reutilización de conexiones  
✅ **Prepared Statements**: Prevención de SQL injection  
✅ **Transaction Management**: Commit/rollback automático  

### Aplicación
✅ **Session-based Auth**: Más rápido que JWT para desktop  
✅ **Template Caching**: Jinja2 cache habilitado  
✅ **Static Asset Serving**: Flask optimizado  
✅ **Lazy Loading**: Datos cargados bajo demanda  

### Frontend
✅ **Vanilla JS**: Sin overhead de frameworks  
✅ **Fetch API**: Moderno y performante  
✅ **CSS Grid/Flexbox**: Layout responsive  
✅ **Local Storage**: Cache de preferencias UI  

## 🔗 Referencias Cruzadas

- [Guía de Desarrollo](DEVELOPMENT.md) - Setup y configuración
- [API REST](API.md) - Endpoints y ejemplos
- [Base de Datos](DATABASE.md) - Esquema y queries
- [Seguridad](SECURITY_ROLES.md) - Roles y permisos
- [Despliegue](DEPLOYMENT.md) - Empaquetado y distribución

## 💡 Mejores Prácticas

### Para Desarrolladores

1. **Siempre usa context managers** para operaciones de BD
2. **Valida en backend** incluso si hay validación en frontend
3. **Usa prepared statements** para todas las queries
4. **Loggea operaciones críticas** (ventas, cambios de stock)
5. **Maneja excepciones** y retorna errores útiles

### Para Mantenimiento

1. **Backup regular** de database.db
2. **Monitorea logs** para detectar problemas temprano
3. **Prueba migraciones** en entorno de staging
4. **Documenta cambios** de esquema en DATABASE.md
5. **Usa git tags** para releases
