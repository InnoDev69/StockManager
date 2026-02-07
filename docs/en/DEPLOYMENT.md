# Deployment / Packaging (Dev)

This document describes how the project binaries are built (Python server + Electron app) and which files participate in packaging.

## Overview

The build happens in two stages:

1. **Python server**: packaged with PyInstaller via [build.spec](../../build.spec), producing `dist/stock-manager-server` (Linux) or `dist/stock-manager-server.exe` (Windows).
2. **Electron**: packaged with electron-builder. The server binary is bundled using `extraResources` (see [package.json](../../package.json)).

## Local build

### 1) Build the server (PyInstaller)

```bash
npm run build:server
```

Expected output:
- Linux: `dist/stock-manager-server`
- Windows: `dist/stock-manager-server.exe`

Important notes:
- The packaged entrypoint is [main.py](../../main.py).
- The spec includes `templates/`, `static/`, `bd/`, `api/` in `datas` (see [build.spec](../../build.spec)).
- The spec currently sets `console=True` (useful for debugging the server binary; releases often switch this to `False`).

### 2) Build the Electron app

Linux:

```bash
npm run build:linux
```

Windows:

```bash
npm run build:win
```

## Electron Builder: included resources

The Electron app bundles the Python server binary as an extra resource:

- Windows (`build.win.extraResources`):
  - `dist/stock-manager-server.exe` → `server/stock-manager-server.exe`
- Linux (`build.linux.extraResources`):
  - `dist/stock-manager-server` → `server/stock-manager-server` (with permissions `0755`)

See configuration in [package.json](../../package.json).

At runtime, the launcher uses:
- `process.resourcesPath/server/<bin>` when packaged (`app.isPackaged === true`)
- `dist/<bin>` in development

Implementation: [electron/python-server.js](../../electron/python-server.js)

## AppImage (Linux)

Dev notes:

- AppImage is mounted under a temporary path (read-only filesystem). Bundled resources must not require write access.
- The server binary must be executable inside the bundle. That is why `permissions: "0755"` is set under `extraResources`.
- If the server needs to write (DB/logs), it must use user-writable paths (see [bd/bdInstance.py](../../bd/bdInstance.py) and [debug/logger.py](../../debug/logger.py)).

### Standalone AppImage with pywebview

In addition to the Electron-based AppImage (main distribution), there is an alternative mode that uses pywebview:

**When to use each?**

- **Electron AppImage (default)**: Includes everything needed, heavier (~150MB) but works on all distros without dependencies.
- **pywebview AppImage**: Lighter alternative for users who prefer a pure Python binary with native Qt/GTK UI.

**Building the standalone AppImage:**

```bash
# From the project root
./build_scripts/build_appimage.sh
```

This script:
1. Creates a Python virtual environment
2. Installs Flask, pywebview, PyQt5 and all dependencies
3. Builds with PyInstaller using `build_appimage.spec`
4. Packages everything into an AppImage with `linuxdeploy` and `appimagetool`
5. Includes necessary QT libraries

**Output:**
- `StockManager-{version}-x86_64.AppImage`

**Testing:**

```bash
# Run test script
./test_appimage.sh

# Or run manually
chmod +x StockManager-*.AppImage
./StockManager-*.AppImage
```

**Relevant files:**
- `build_scripts/build_appimage.sh` - Build script
- `build_appimage.spec` - PyInstaller config for pywebview
- `launcher_pywebview.py` - Python launcher with pywebview
- `StockManager.desktop` - Desktop entry
- `test_appimage.sh` - Test script

**Note:** The standalone AppImage requires QT/GTK dependencies to be included in the bundle. The build script handles this automatically.


## CI/CD (GitHub Actions)

The pipeline is in [.github/workflows/build.yml](../../.github/workflows/build.yml) and runs when pushing a `v*.*.*` tag.

Summary:

- Syncs `package.json` version with the tag (e.g. `v1.2.3` → `1.2.3`).
- Installs:
  - Python 3.11 (in CI)
  - Node 20
- Builds the server with `pyinstaller build.spec`.
- Builds Electron for Linux (AppImage + deb) and Windows (nsis).
- Uploads artifacts and creates a GitHub Release.

Dev note: your local environment can be Python 3.13, but CI uses 3.11.

## Note about the port

Electron tries to pick a free port and passes `--port` to the server binary. The packaged Flask server currently reads the port from `FLASK_PORT` (default 5000), not from `--port`.

This can break when `5000` is already in use (Electron will pick a different port and the UI will not connect).

See details in [docs/en/ARCHITECTURE.md](ARCHITECTURE.md).
