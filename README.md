# Stock Manager

Sistema de gestión de inventario y ventas con interfaz web.

## 📦 Instalación

### Windows

Descarga el instalador desde [Releases](../../releases):
- `Stock Manager Setup.exe` - Instalador completo

```bash
# Ejecuta el instalador y sigue las instrucciones
```

### Linux

#### Opción 1: AppImage (Recomendado)

Descarga el AppImage desde [Releases](../../releases):

```bash
# Hacer ejecutable
chmod +x stock-manager-*.AppImage

# Ejecutar
./stock-manager-*.AppImage
```

**Ventajas:**
- Un solo archivo portable
- Funciona en todas las distribuciones
- No requiere instalación
- Incluye todas las dependencias

#### Opción 2: Paquete DEB (Debian/Ubuntu/Mint)

```bash
sudo dpkg -i stock-manager_*.deb
sudo apt-get install -f  # Resolver dependencias si es necesario
```

#### Opción 3: AppImage Standalone con pywebview

Para una versión más ligera con UI nativa Qt/GTK:

```bash
git clone https://github.com/InnoDev69/StockManager.git
cd StockManager
./build_scripts/build_appimage.sh
```

Esto generará `StockManager-{version}-x86_64.AppImage` con todas las dependencias incluidas.

## 🚀 Desarrollo

### Requisitos

- Python 3.11+
- Node.js 20+
- npm

### Configuración

```bash
# Clonar repositorio
git clone https://github.com/InnoDev69/StockManager.git
cd StockManager

# Instalar dependencias Python
pip install -r requirements.txt

# Instalar dependencias Node
npm install

# Ejecutar en modo desarrollo
npm start
```

### Build

#### Servidor Python

```bash
npm run build:server
```

#### Aplicación Electron

**Linux:**
```bash
npm run build:linux
```

**Windows:**
```bash
npm run build:win
```

#### AppImage Standalone

```bash
./build_scripts/build_appimage.sh
```

Ver [build_scripts/README.md](build_scripts/README.md) para más detalles.

## 📚 Documentación

- [Español](docs/es/README.md)
- [English](docs/en/README.md)

### Guías de Desarrollo

- [Arquitectura](docs/es/ARCHITECTURE.md)
- [Desarrollo](docs/es/DEVELOPMENT.md)
- [Despliegue](docs/es/DEPLOYMENT.md)
- [API](docs/es/API.md)
- [Base de datos](docs/es/DATABASE.md)
- [Troubleshooting](docs/es/TROUBLESHOOTING.md)

## 🐛 Troubleshooting

### Error: "QT cannot be loaded" o "GTK cannot be loaded"

Este error ocurre con el AppImage standalone de pywebview. Soluciones:

1. **Usar el AppImage de Electron** (distribución por defecto) - no requiere dependencias adicionales
2. **Instalar dependencias manualmente:**

```bash
# Arch Linux
sudo pacman -S python-pyqt5 python-pyqt5-webengine

# Ubuntu/Debian
sudo apt install python3-pyqt5 python3-pyqt5.qtwebengine
```

Ver [docs/es/TROUBLESHOOTING.md](docs/es/TROUBLESHOOTING.md#errores-de-qtgtk-con-pywebview-modo-standalone) para más detalles.

### Error: "ERR_CONNECTION_REFUSED"

Ver [docs/es/TROUBLESHOOTING.md](docs/es/TROUBLESHOOTING.md#electron-err_connection_refused-al-abrir-la-app).

## 🔧 Características

- ✅ Gestión de inventario
- ✅ Registro de ventas
- ✅ Control de usuarios y roles
- ✅ Importación CSV
- ✅ Reportes y métricas
- ✅ API REST
- ✅ Multi-plataforma (Windows, Linux)

## 📄 Licencia

MIT License - Ver [LICENSE](LICENSE) para más detalles.

## 👤 Autor

**InnoDev69**
- GitHub: [@InnoDev69](https://github.com/InnoDev69)
- Email: yamirnu14@proton.me
