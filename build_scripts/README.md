# Build Scripts

Scripts para construir StockManager en diferentes formatos de distribución.

## build_appimage.sh

Script para construir un AppImage standalone de StockManager con pywebview.

**Requisitos:**
- Python 3.11+
- `python3-venv` instalado
- Acceso a internet (descarga herramientas AppImage)

**Uso:**
```bash
./build_scripts/build_appimage.sh
```

**Variables de entorno:**
- `VERSION` - Versión del AppImage (default: 1.1.0)

**Salida:**
- `StockManager-{VERSION}-x86_64.AppImage`

**Qué hace:**
1. Crea un entorno virtual Python
2. Instala todas las dependencias (Flask, pywebview, PyQt5)
3. Construye el ejecutable con PyInstaller usando `build_appimage.spec`
4. Crea la estructura AppDir
5. Descarga `linuxdeploy` y `appimagetool` si no existen
6. Empaqueta todo en un AppImage portable

**Características del AppImage resultante:**
- Incluye Python embebido
- Incluye todas las dependencias de QT/GTK
- Funciona en múltiples distros Linux sin instalación
- Portable - un solo archivo ejecutable
- Funciona en Arch Linux, Ubuntu, Fedora, Debian, etc.

## test_appimage.sh

Script para probar el AppImage generado.

**Uso:**
```bash
./test_appimage.sh
```

**Qué verifica:**
- Permisos de ejecución
- Estructura interna del AppImage
- Archivos críticos (ejecutable, desktop entry, icono)
- Dependencias de PyQt5/GTK
- Ejecución rápida (5 segundos)

## Diferencias entre distribuciones

### Electron AppImage (distribución principal)
- Construido con: `npm run build:linux`
- Incluye: Electron + Flask server
- Tamaño: ~150MB
- Ventajas: Probado, estable, incluye todo
- Desventajas: Más pesado

### pywebview AppImage (alternativa)
- Construido con: `./build_scripts/build_appimage.sh`
- Incluye: Python + Flask + pywebview + PyQt5
- Tamaño: ~80-100MB
- Ventajas: Más ligero, UI nativa
- Desventajas: Menos probado

## Troubleshooting

### Error: "QT cannot be loaded"
El AppImage debe incluir PyQt5. Verifica que el script instale correctamente:
```bash
pip install PyQt5 PyQtWebEngine
```

### Error: "unable to open database file"
El AppImage monta en modo solo lectura. La base de datos debe estar en:
- `~/.stock_manager/data/database.db`

Ver `bd/bdInstance.py` para la lógica de rutas.

### Error descargando herramientas
Verifica conexión a internet y que GitHub esté accesible:
- https://github.com/linuxdeploy/linuxdeploy/releases
- https://github.com/AppImage/AppImageKit/releases

## Referencias

- [AppImage Documentation](https://docs.appimage.org/)
- [linuxdeploy](https://github.com/linuxdeploy/linuxdeploy)
- [PyInstaller](https://pyinstaller.org/)
- [pywebview](https://pywebview.flowrl.com/)
