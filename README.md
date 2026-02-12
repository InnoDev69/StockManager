# 📦 StockManager

> Sistema profesional de gestión de inventarios y ventas con interfaz desktop nativa

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-3.0.0-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## 🎯 Descripción

StockManager es una aplicación de escritorio para la gestión integral de inventarios y ventas, diseñada para pequeñas y medianas empresas que necesitan control total sobre su inventario sin complicaciones de configuración.

### ✨ Características Principales

- **📊 Dashboard Intuitivo**: Vista general con métricas en tiempo real
- **🔐 Sistema de Autenticación**: Control de acceso basado en roles
- **📦 Gestión de Productos**: CRUD completo con códigos de barras
- **💰 Registro de Ventas**: Procesamiento rápido con actualización automática
- **📈 Métricas y Reportes**: Análisis de ventas y tendencias
- **📥 Importación CSV**: Carga masiva de productos
- **🔍 Búsqueda Avanzada**: Filtrado por múltiples criterios
- **📱 Interfaz Responsiva**: Adaptable a diferentes pantallas
- **🔒 Seguridad**: Contraseñas hasheadas y validación exhaustiva

## 🚀 Inicio Rápido

### Requisitos

- **Python 3.8+**
- **pip** (gestor de paquetes)
- **SQLite 3** (incluido en Python)

### Instalación

```bash
# 1. Clonar el repositorio
git clone https://github.com/InnoDev69/StockManager.git
cd StockManager

# 2. Crear entorno virtual
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Ejecutar la aplicación
python main.py
```

La aplicación se abrirá automáticamente en una ventana nativa en `http://127.0.0.1:5000`

### 🎯 Primer Uso

1. **Registro**: Crear cuenta en la pantalla de registro
2. **Login**: Iniciar sesión con credenciales
3. **Agregar Productos**: Navegar a "Nuevo Producto"
4. **Registrar Ventas**: Usar formulario de ventas
5. **Ver Dashboard**: Monitorear estadísticas

## 📚 Documentación

### Para Desarrolladores

- **[Español](docs/es/README.md)** - Documentación completa en español
- **[English](docs/en/README.md)** - Full English documentation

#### Guías Principales

- [🏗️ Arquitectura](docs/es/ARCHITECTURE.md) - Diseño del sistema
- [🔧 Desarrollo](docs/es/DEVELOPMENT.md) - Setup del entorno
- [📡 API REST](docs/es/API.md) - Endpoints y ejemplos
- [💾 Base de Datos](docs/es/DATABASE.md) - Esquema y queries
- [🔒 Seguridad](docs/es/SECURITY_ROLES.md) - Roles y permisos
- [📦 Despliegue](docs/es/DEPLOYMENT.md) - Empaquetado
- [🛠️ Troubleshooting](docs/es/TROUBLESHOOTING.md) - Soluciones

## 🏗️ Arquitectura

```
┌─────────────────────────────────────┐
│      PyWebView Window               │
│  ┌───────────────────────────────┐  │
│  │    Interfaz Web (HTML/CSS/JS) │  │
│  └───────────────────────────────┘  │
└─────────────┬───────────────────────┘
              ↕ HTTP
    http://127.0.0.1:5000
              ↕
┌─────────────▼───────────────────────┐
│       Flask Application             │
│  ┌──────────┐    ┌───────────────┐ │
│  │   UI     │    │   API REST    │ │
│  │ (Jinja2) │    │   (/api/*)    │ │
│  └──────────┘    └───────────────┘ │
└─────────────┬───────────────────────┘
              ↕
┌─────────────▼───────────────────────┐
│      SQLite Database                │
│      (database.db)                  │
└─────────────────────────────────────┘
```

**Componentes:**
- **Frontend**: PyWebView (ventana nativa) + HTML/CSS/JS
- **Backend**: Flask 3.0.0 (Python)
- **Base de Datos**: SQLite 3 con WAL mode
- **API**: REST JSON endpoints

Ver [ARCHITECTURE.md](docs/es/ARCHITECTURE.md) para detalles completos.

## 🔌 API REST

La aplicación expone una API REST completa:

### Endpoints Principales

```http
GET  /api/health              # Estado del servidor
GET  /api/products            # Listar productos activos
GET  /api/products/:id        # Obtener producto
POST /api/products            # Crear producto (admin)
PUT  /api/products/:id        # Actualizar producto (admin)
DELETE /api/products/:id      # Eliminar producto (admin)
POST /api/sales               # Registrar venta
GET  /api/sales               # Historial de ventas
GET  /api/stats               # Estadísticas del dashboard
```

**Ejemplo:**
```javascript
// Obtener productos
fetch('/api/products')
  .then(r => r.json())
  .then(products => console.log(products));
```

📖 Ver [documentación completa de la API](docs/es/API.md)

## 🛠️ Tecnologías

### Backend
- **Python 3.8+**
- **Flask 3.0.0** - Framework web
- **SQLite 3** - Base de datos
- **Werkzeug 3.0.1** - Seguridad
- **PyWebView** - Desktop wrapper

### Frontend
- **HTML5 + Jinja2** - Templates
- **CSS3** - Estilos (vanilla)
- **JavaScript ES6+** - Interactividad
- **Fetch API** - AJAX requests

## 📊 Estructura del Proyecto

```
StockManager/
├── main.py                 # Entrypoint principal
├── requirements.txt        # Dependencias Python
├── .gitignore             # Archivos ignorados
│
├── api/
│   └── API.py             # Blueprint REST API
│
├── bd/                     # Capa de base de datos
│   ├── bdConector.py      # Conector SQLite
│   ├── bdInstance.py      # Instancia global
│   └── bdErrors.py        # Excepciones
│
├── data/                   # Validación
│   ├── validators.py      # Validadores
│   └── limits.py          # Límites
│
├── tools/                  # Utilidades
│   ├── logger.py          # Sistema de logging
│   ├── scheduler.py       # Tareas periódicas
│   └── timmer.py          # Medición de rendimiento
│
├── templates/              # Plantillas HTML
│   ├── dashboard.html     # Dashboard principal
│   ├── login.html         # Login/Registro
│   └── ...
│
├── static/                 # Assets estáticos
│   ├── css/
│   ├── js/
│   └── app/               # Íconos
│
└── docs/                   # Documentación
    ├── es/                # Español
    └── en/                # English
```

## 🔒 Seguridad

- ✅ **Contraseñas**: Hasheadas con PBKDF2:SHA256
- ✅ **Sesiones**: Cookies firmadas
- ✅ **Validación**: Todos los inputs validados
- ✅ **SQL Injection**: Queries parametrizadas
- ✅ **Foreign Keys**: Integridad referencial
- ✅ **CSRF**: Protección nativa de Flask

## 🤝 Contribuir

Las contribuciones son bienvenidas:

1. Fork el repositorio
2. Crea una rama (`git checkout -b feature/NuevaCaracteristica`)
3. Commit cambios (`git commit -m 'Add: nueva característica'`)
4. Push a la rama (`git push origin feature/NuevaCaracteristica`)
5. Abre un Pull Request

### Guía de Estilo

- **Python**: PEP 8
- **Docstrings**: Google Style
- **Commits**: Mensajes descriptivos en presente

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Ver archivo [LICENSE](LICENSE) para detalles.

## 👥 Autores

- **InnoDev69** - [GitHub](https://github.com/InnoDev69)

## 📞 Soporte

Si encuentras problemas:

1. Revisa [Troubleshooting](docs/es/TROUBLESHOOTING.md)
2. Busca en [Issues](https://github.com/InnoDev69/StockManager/issues)
3. Abre un [nuevo issue](https://github.com/InnoDev69/StockManager/issues/new)

---

⭐ Si este proyecto te resulta útil, considera darle una estrella en GitHub
