# Despliegue / Empaquetado (Dev)

Este documento describe cómo se construyen los binarios del proyecto (servidor Python + app Electron) y qué archivos participan en el empaquetado.

## Visión general

El build se hace en dos etapas:

1. **Servidor Python**: se empaqueta con PyInstaller desde [build.spec](../../build.spec) y genera `dist/stock-manager-server` (Linux) o `dist/stock-manager-server.exe` (Windows).
2. **Electron**: se empaqueta con electron-builder. El binario del servidor se copia dentro del bundle usando `extraResources` (ver [package.json](../../package.json)).

## Build local

### 1) Construir el servidor (PyInstaller)

```bash
npm run build:server
```

Salida esperada:
- Linux: `dist/stock-manager-server`
- Windows: `dist/stock-manager-server.exe`

Notas importantes:
- El entrypoint empaquetado es [main.py](../../main.py).
- El spec incluye `templates/`, `static/`, `bd/`, `api/` en `datas` (ver [build.spec](../../build.spec)).
- El spec tiene `console=True` (útil para debug del binario; en releases suele ponerse `False`).

### 2) Construir la app Electron

Linux:

```bash
npm run build:linux
```

Windows:

```bash
npm run build:win
```

## Electron Builder: recursos incluidos

La app Electron incluye el binario del servidor Python como recurso extra:

- Windows (`build.win.extraResources`):
  - `dist/stock-manager-server.exe` → `server/stock-manager-server.exe`
- Linux (`build.linux.extraResources`):
  - `dist/stock-manager-server` → `server/stock-manager-server` (con permisos `0755`)

Ver configuración en [package.json](../../package.json).

En runtime, el launcher usa:
- `process.resourcesPath/server/<bin>` cuando está empaquetado (`app.isPackaged === true`)
- `dist/<bin>` cuando está en desarrollo

Implementación: [electron/python-server.js](../../electron/python-server.js)

## AppImage (Linux)

Notas relevantes para dev:

- AppImage se monta en una ruta temporal (filesystem de solo lectura). Los recursos del bundle no deben necesitar escritura.
- El binario del servidor debe ser ejecutable dentro del bundle. Por eso se fuerza `permissions: "0755"` en `extraResources`.
- Si el servidor necesita escribir (DB/logs), debe hacerlo en rutas escribibles del usuario (ver [bd/bdInstance.py](../../bd/bdInstance.py) y [debug/logger.py](../../debug/logger.py)).

### AppImage Standalone con pywebview

Además del AppImage basado en Electron (distribución principal), existe un modo alternativo que usa pywebview:

**¿Cuándo usar cada uno?**

- **Electron AppImage (por defecto)**: Incluye todo lo necesario, más pesado (~150MB) pero funciona en todas las distros sin dependencias.
- **pywebview AppImage**: Alternativa más ligera para usuarios que prefieren un binario Python puro con UI nativa Qt/GTK.

**Construcción del AppImage standalone:**

```bash
# Desde la raíz del proyecto
./build_scripts/build_appimage.sh
```

Este script:
1. Crea un entorno Python virtual
2. Instala Flask, pywebview, PyQt5 y todas las dependencias
3. Construye con PyInstaller usando `build_appimage.spec`
4. Empaqueta todo en un AppImage con `linuxdeploy` y `appimagetool`
5. Incluye las librerías de QT necesarias

**Salida:**
- `StockManager-{version}-x86_64.AppImage`

**Pruebas:**

```bash
# Ejecutar script de test
./test_appimage.sh

# O ejecutar manualmente
chmod +x StockManager-*.AppImage
./StockManager-*.AppImage
```

**Archivos relevantes:**
- `build_scripts/build_appimage.sh` - Script de construcción
- `build_appimage.spec` - Configuración PyInstaller para pywebview
- `launcher_pywebview.py` - Launcher Python con pywebview
- `StockManager.desktop` - Desktop entry
- `test_appimage.sh` - Script de pruebas

**Nota:** El AppImage standalone requiere que las dependencias de QT/GTK estén incluidas en el bundle. El script de construcción se encarga de esto automáticamente.


## CI/CD (GitHub Actions)

El pipeline vive en [.github/workflows/build.yml](../../.github/workflows/build.yml) y corre cuando se pushea un tag `v*.*.*`.

Resumen:

- Sincroniza la versión de `package.json` con el tag (ej. `v1.2.3` → `1.2.3`).
- Instala:
  - Python 3.11 (en CI)
  - Node 20
- Construye el servidor con `pyinstaller build.spec`.
- Construye Electron para Linux (AppImage + deb) y Windows (nsis).
- Publica artefactos y crea un GitHub Release.

Nota para dev: tu entorno local puede ser Python 3.13, pero CI usa 3.11.

## Nota sobre el puerto

Electron intenta elegir un puerto libre y pasa `--port` al binario del servidor. El servidor Flask empaquetado actualmente lee el puerto de `FLASK_PORT` (default 5000), no de `--port`.

Esto puede causar problemas si `5000` está ocupado (Electron elegirá otro puerto y la UI no conectará).

Ver detalle en [docs/es/ARCHITECTURE.md](ARCHITECTURE.md).
