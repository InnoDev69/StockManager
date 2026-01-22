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

