# Troubleshooting

Quick guide to diagnose common issues in development and packaged builds (especially Linux/AppImage).

## Electron: `ERR_CONNECTION_REFUSED` when opening the app

Symptoms:
- Electron tries to load `http://127.0.0.1:<port>` and fails with `ERR_CONNECTION_REFUSED`.
- Logs show the server “starts” and then exits with a non-zero code.

Checklist:

1) **Confirm the server process is actually alive**
- The process is launched from `electron/python-server.js`.
- If the binary exits immediately, Electron can’t load the UI.

2) **Check Python logs**
- In packaged mode (PyInstaller), logs are written to:
  - Linux/macOS: `~/.stock_manager/logs/app_YYYYMMDD.log`
  - Windows: `%APPDATA%/StockManager/logs/app_YYYYMMDD.log`
- In development: `./logs/app_YYYYMMDD.log`

3) **Embedded binary permissions (Linux/AppImage)**
- The embedded server must be executable (`chmod +x`).
- The `electron-builder` config includes `extraResources.permissions = "0755"` for the Linux server binary.
- If it still fails: inspect the AppImage contents and verify the extracted file permissions.

## Port mismatch (very important)

Current behavior:
- Electron selects a free port starting at 5000 and launches the server with `--port <port>`.
- The Flask server (in `main.py`) reads the port from `FLASK_PORT` (default 5000) and **does not parse `--port`**.

Consequence:
- If Electron picks a port different from 5000, Flask may still bind to 5000 and Electron will point to the wrong port.

Workarounds:
- Force `FLASK_PORT=5000` and avoid the launcher selecting another port.
- Or (proper fix) implement argument parsing in the server to accept `--port`.

## AppImage: path / write-to-disk issues

In frozen mode the server creates the DB at `data/database.db` next to the executable (`sys.executable`).

In AppImage, the executable directory may live inside a temporary mount that is often **read-only**.

Typical symptoms:
- The server exits during startup.
- Logs show `OperationalError: unable to open database file` or similar.

Recommended mitigation:
- Move the DB to a writable user directory (similar to how logs are handled).
- At minimum, allow configuring `DB_PATH` in frozen mode as well.

## You can’t see the real server error (stdout/stderr hidden)

In `electron/python-server.js` the child process is spawned with `stdio: 'ignore'`, which hides stdout/stderr.

For debugging:
- Temporarily change `stdio` to `'pipe'` and log `child.stdout`/`child.stderr`, or to `'inherit'` to see output in the console.
- Run the server binary manually from a terminal and inspect the generated log file.

## Template / routing errors (Flask)

If the app starts but crashes when navigating:
- Check the log for the day.
- Common issue: `BuildError` from `url_for()` pointing to a missing endpoint.

## QT/GTK errors with pywebview (standalone mode)

**Symptoms:**
```
[pywebview] QT cannot be loaded
ModuleNotFoundError: No module named 'qtpy'
[pywebview] GTK cannot be loaded
ValueError: Namespace Gtk not available
webview.errors.WebViewException: You must have either QT or GTK with Python extensions installed
```

**Context:**
- This error occurs when using the standalone launcher with pywebview (`launcher_pywebview.py`)
- It does **NOT affect** the normal Electron mode (standard StockManager distribution)
- pywebview requires a graphical backend: PyQt5 or GTK

**Solution 1: Use AppImage (recommended)**

The standalone AppImage includes all dependencies:

```bash
# Download the AppImage from releases
chmod +x StockManager-*.AppImage
./StockManager-*.AppImage
```

**Solution 2: Install dependencies manually**

For PyQt5 (recommended):
```bash
# Arch Linux
sudo pacman -S python-pyqt5 python-pyqt5-webengine

# Ubuntu/Debian
sudo apt install python3-pyqt5 python3-pyqt5.qtwebengine

# With pip (any distro)
pip install PyQt5 PyQtWebEngine pywebview
```

For GTK (alternative):
```bash
# Arch Linux
sudo pacman -S python-gobject gtk3 webkit2gtk

# Ubuntu/Debian
sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.0

# With pip (requires system dependencies)
pip install PyGObject pywebview
```

**Solution 3: Use Electron mode (default)**

The standard distribution uses Electron, not pywebview:
```bash
# Download the installer/AppImage from releases
# Electron includes everything needed without extra dependencies
```

**Verify installation:**

```bash
python3 -c "import webview; print('pywebview:', webview.__version__)"
python3 -c "from PyQt5 import QtCore; print('PyQt5 OK')"
```

