# 📦 StockManager

> Sistema profesional de gestión de inventarios y ventas con interfaz web moderna

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0.0-green.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 📋 Descripción

StockManager es una aplicación de escritorio para la gestión integral de inventarios y ventas, diseñada para pequeñas y medianas empresas. Combina la simplicidad de una interfaz web moderna con la potencia de una aplicación nativa, ofreciendo control total sobre productos, ventas y reportes.

### ✨ Características Principales

- **📊 Dashboard Intuitivo**: Vista general del estado del inventario con métricas en tiempo real
- **🔐 Sistema de Autenticación**: Control de acceso basado en roles (Admin/Vendedor)
- **📦 Gestión de Productos**: CRUD completo con códigos de barras y alertas de stock bajo
- **💰 Registro de Ventas**: Procesamiento rápido de ventas con actualización automática de inventario
- **📈 Métricas y Reportes**: Análisis de ventas y tendencias del inventario
- **📥 Importación CSV**: Carga masiva de productos desde archivos CSV con mapeo flexible de columnas
- **🔍 Búsqueda Avanzada**: Filtrado y búsqueda de productos por múltiples criterios
- **📱 Interfaz Responsiva**: Diseño adaptable a diferentes tamaños de pantalla
- **🔒 Seguridad**: Contraseñas hasheadas con Werkzeug y validación exhaustiva de datos
- **📝 Logging Completo**: Sistema de logs para auditoría y diagnóstico

## 🚀 Inicio Rápido

### Requisitos Previos

- **Python 3.8+**
- **pip** (gestor de paquetes de Python)
- **SQLite 3** (incluido por defecto en Python)

### Instalación

1. **Clonar el repositorio**

```bash
git clone https://github.com/InnoDev69/StockManager.git
cd StockManager
```

2. **Crear entorno virtual** (recomendado)

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/macOS
python3 -m venv venv
source venv/bin/activate
```

3. **Instalar dependencias**

```bash
pip install -r requirements.txt
```

4. **Configurar variables de entorno** (opcional)

Crear archivo `.env` en la raíz del proyecto:

```env
FLASK_SECRET_KEY=tu_clave_secreta_aqui
FLASK_PORT=5000
DEBUG=0
```

5. **Ejecutar la aplicación**

```bash
python main.py
```

La aplicación se abrirá automáticamente en una ventana nativa en `http://127.0.0.1:5000`

### 🎯 Primer Uso

1. **Registro**: Crear una cuenta de usuario en la pantalla de registro
2. **Login**: Iniciar sesión con las credenciales creadas
3. **Agregar Productos**: Navegar a "Nuevo Producto" para agregar items al inventario
4. **Registrar Ventas**: Usar el formulario de ventas para procesar transacciones
5. **Ver Dashboard**: Monitorear estadísticas y productos con stock bajo

## 📚 Documentación

### Documentación para Desarrolladores

La documentación completa está disponible en dos idiomas:

- **[Español](docs/es/README.md)** - Documentación en español
- **[English](docs/en/README.md)** - English documentation

#### Guías Principales

- [🏗️ Arquitectura del Sistema](docs/es/ARCHITECTURE.md) - Diseño y componentes
- [🔧 Guía de Desarrollo](docs/es/DEVELOPMENT.md) - Configuración del entorno de desarrollo
- [📡 Documentación de API](docs/es/API.md) - Endpoints REST y ejemplos
- [💾 Base de Datos](docs/es/DATABASE.md) - Esquema y operaciones
- [🔒 Roles y Permisos](docs/es/SECURITY_ROLES.md) - Sistema de autorización
- [📦 Despliegue](docs/es/DEPLOYMENT.md) - Empaquetado y distribución
- [🔍 Tour del Repositorio](docs/es/REPO_TOUR.md) - Estructura del proyecto
- [🛠️ Troubleshooting](docs/es/TROUBLESHOOTING.md) - Solución de problemas comunes

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────┐
│        Aplicación de Escritorio         │
│            (Python + Flask)              │
├─────────────────────────────────────────┤
│                                         │
│  ┌──────────────┐    ┌──────────────┐  │
│  │   Frontend   │    │   API REST   │  │
│  │   (Jinja2)   │◄──►│   (Flask)    │  │
│  │  Templates   │    │   Blueprint  │  │
│  └──────────────┘    └──────────────┘  │
│         │                    │          │
│         └────────┬───────────┘          │
│                  │                      │
│         ┌────────▼────────┐             │
│         │  Capa de Datos  │             │
│         │   (BDConector)  │             │
│         └────────┬────────┘             │
│                  │                      │
│         ┌────────▼────────┐             │
│         │   SQLite DB     │             │
│         │  (stock.db)     │             │
│         └─────────────────┘             │
│                                         │
└─────────────────────────────────────────┘
```

### Estructura del Proyecto

```
StockManager/
├── api/                    # API REST Blueprint
│   └── API.py             # Endpoints JSON
├── bd/                    # Capa de base de datos
│   ├── bdConector.py      # Conector SQLite con transacciones
│   ├── bdInstance.py      # Instancia global de BD
│   └── bdErrors.py        # Excepciones personalizadas
├── data/                  # Validación y reglas de negocio
│   ├── validators.py      # Validadores de entrada
│   └── limits.py          # Límites y constantes
├── docs/                  # Documentación del proyecto
│   ├── es/               # Documentación en español
│   └── en/               # English documentation
├── static/               # Assets estáticos (CSS, JS, imágenes)
├── templates/            # Plantillas HTML (Jinja2)
├── tools/                # Utilidades
│   ├── logger.py         # Sistema de logging
│   ├── scheduler.py      # Tareas programadas
│   └── timmer.py         # Medición de rendimiento
├── main.py               # Punto de entrada de la aplicación
├── requirements.txt      # Dependencias de Python
└── README.md            # Este archivo
```

## 🔌 API REST

La aplicación expone una API REST para operaciones programáticas:

### Endpoints Principales

```
GET  /api/health              # Estado del servidor
GET  /api/products_all        # Listar todos los productos
GET  /api/products/:id        # Obtener producto por ID
POST /api/products            # Crear nuevo producto
PUT  /api/products/:id        # Actualizar producto
DELETE /api/products/:id      # Eliminar producto
GET  /api/sales               # Historial de ventas
POST /api/sales               # Registrar nueva venta
```

📖 Ver [documentación completa de la API](docs/es/API.md) para detalles y ejemplos.

## 🛠️ Tecnologías

- **Backend**: Flask 3.0.0, Python 3.8+
- **Base de Datos**: SQLite 3 con modo WAL
- **Frontend**: HTML5, CSS3, JavaScript (Vanilla)
- **Seguridad**: Werkzeug (password hashing), validación de entrada
- **Logging**: Sistema de logs rotativo con niveles configurables

## 📦 Dependencias Principales

```
Flask==3.0.0              # Framework web
Werkzeug==3.0.1          # Utilidades WSGI y seguridad
python-dotenv==1.0.0     # Gestión de variables de entorno
```

Ver [requirements.txt](requirements.txt) para la lista completa.

## 🔒 Seguridad

- **Contraseñas**: Hasheadas con `pbkdf2:sha256` (Werkzeug)
- **Sesiones**: Cookies firmadas con clave secreta
- **Validación**: Todos los inputs son validados antes de procesarse
- **SQL Injection**: Protección mediante consultas parametrizadas
- **Foreign Keys**: Integridad referencial habilitada en SQLite
- **CSRF**: Protección nativa de Flask para formularios

## 🤝 Contribuir

Las contribuciones son bienvenidas. Por favor:

1. Fork el repositorio
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

### Guía de Estilo

- **Python**: Seguir PEP 8
- **Docstrings**: Formato Google Style
- **Commits**: Mensajes descriptivos en presente ("Add feature" no "Added feature")

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Ver archivo [LICENSE](LICENSE) para más detalles.

## 👥 Autores

- **InnoDev69** - [GitHub](https://github.com/InnoDev69)

## 🙏 Agradecimientos

- Flask y la comunidad de Python
- Todos los contribuidores del proyecto

## 📞 Soporte

Si encuentras algún problema o tienes preguntas:

1. Revisa la [guía de troubleshooting](docs/es/TROUBLESHOOTING.md)
2. Busca en los [issues existentes](https://github.com/InnoDev69/StockManager/issues)
3. Abre un [nuevo issue](https://github.com/InnoDev69/StockManager/issues/new) con detalles del problema

---

⭐ Si este proyecto te resulta útil, considera darle una estrella en GitHub
